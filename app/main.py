"""FastAPI application factory per docs_product-design.md."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import build_app_state
from app.api.v1 import (
    buckets,
    client_config,
    directory_uploads,
    files,
    health,
    lifecycle,
    presign,
    settings as settings_api,
    uploads,
)
from app.config.loader import load_settings
from app.config.validation import validate_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, request_id_var

logger = logging.getLogger("upload_service.api")

_HEALTH_PATHS = frozenset({"/healthz", "/readyz", "/startupz", "/health", "/metrics"})


def _log_request_outcome(request: Request, status_code: int, started: float) -> None:
    """Log every HTTP request outcome (skips healthy probes; reports failures)."""
    path = request.url.path
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    fields = {
        "method": request.method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }
    if path in _HEALTH_PATHS:
        if status_code >= 400:
            logger.warning("health check failed", extra={"extra_fields": fields})
        return
    if status_code >= 400:
        logger.warning("request failed", extra={"extra_fields": fields})
    else:
        logger.info("request completed", extra={"extra_fields": fields})


def create_app(settings: Any = None, config_path: str | None = None) -> FastAPI:
    if settings is None:
        settings = load_settings(config_path)
    validation = validate_settings(settings)
    if not validation.ok:
        raise ValueError("invalid configuration:\n- " + "\n- ".join(validation.errors))
    configure_logging(
        level=settings.logging.level,
        fmt=settings.logging.format,
        log_center=settings.log_center,
    )

    state = build_app_state(settings)
    url = (settings.database.url or "").lower()
    if settings.app.environment in ("development", "test") or url.startswith("sqlite"):
        from app.db.session import create_tables

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop (tests, CLI): create eagerly so in-process
            # transports that skip lifespan still find tables.
            asyncio.run(create_tables(state.engine))
        # Under uvicorn the factory runs inside the serving loop; tables are
        # created by the lifespan below before the first request is served.

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.app.environment in ("development", "test") or (
            settings.database.url or ""
        ).lower().startswith("sqlite"):
            from app.db.session import create_tables

            await create_tables(state.engine)
        yield
        await state.engine.dispose()

    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.state = state

    origins = settings.portal.origins or []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.portal.cors.allow_credentials,
        allow_methods=settings.portal.cors.allow_methods,
        allow_headers=settings.portal.cors.allow_headers,
        expose_headers=settings.portal.cors.expose_headers,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            import uuid

            request_id = f"req-{uuid.uuid4().hex[:16]}"
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            _log_request_outcome(request, response.status_code, started)
            return response
        except Exception:
            logger.exception(
                "unhandled exception",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": request.url.path,
                    }
                },
            )
            raise
        finally:
            request_id_var.reset(token)

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(files.router, prefix="/v1")
    app.include_router(uploads.router, prefix="/v1")
    app.include_router(directory_uploads.router, prefix="/v1")
    app.include_router(lifecycle.router, prefix="/v1")
    app.include_router(presign.router, prefix="/v1")
    app.include_router(client_config.router, prefix="/v1")
    app.include_router(buckets.router, prefix="/v1")
    app.include_router(settings_api.router, prefix="/v1")
    return app
