"""Cleanup worker loop: expired sessions, stale multipart dirs, idempotency records."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.cleanup_service import CleanupService

logger = logging.getLogger("upload_service.worker.cleanup")


async def cleanup_loop(
    session_factory: async_sessionmaker[AsyncSession],
    service: CleanupService,
    *,
    interval_seconds: int = 300,
    batch_size: int = 100,
) -> None:
    while True:
        try:
            async with session_factory() as session:
                expired = await service.expire_upload_sessions(session, batch_size=batch_size)
                idem = await service.expire_idempotency_records(session, batch_size=batch_size)
                await session.commit()
            if expired or idem:
                logger.info("cleanup: expired sessions=%d idempotency=%d", expired, idem)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("cleanup loop iteration failed")
        await asyncio.sleep(interval_seconds)
