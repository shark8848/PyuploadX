"""Worker process entrypoint: runs background task loops (docs section 21)."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from app.config.loader import load_settings
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory
from app.services.cleanup_service import CleanupService
from app.services.reconcile_service import ReconcileService
from app.storage.factory import build_storage
from app.worker.cleanup import cleanup_loop
from app.worker.lifecycle import lifecycle_loop


logger = logging.getLogger("upload_service.worker")


async def _run_worker(settings: Any) -> None:
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    storage = build_storage(settings)
    cleanup = CleanupService(settings)
    reconcile = ReconcileService(storage)

    tasks: list[asyncio.Task] = []
    if settings.worker.enabled:
        if settings.worker.cleanup.enabled:
            tasks.append(
                asyncio.create_task(
                    cleanup_loop(
                        session_factory,
                        cleanup,
                        interval_seconds=settings.worker.cleanup.interval_seconds,
                    ),
                    name="cleanup",
                )
            )
        if settings.lifecycle.worker.enabled:
            tasks.append(
                asyncio.create_task(
                    lifecycle_loop(
                        session_factory,
                        storage,
                        interval_seconds=settings.lifecycle.worker.scan_interval_seconds,
                        batch_size=settings.lifecycle.worker.batch_size,
                    ),
                    name="lifecycle",
                )
            )
    logger.info("worker started with %d task(s)", len(tasks))
    stop = asyncio.Event()

    def _shutdown() -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass
    try:
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await engine.dispose()


def main() -> None:
    settings = load_settings()
    configure_logging(level=settings.logging.level, fmt=settings.logging.format)
    asyncio.run(_run_worker(settings))


if __name__ == "__main__":
    main()
