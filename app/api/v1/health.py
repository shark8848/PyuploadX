"""Health, readiness, startup and metrics endpoints (docs 16.1, 23.3)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.dependencies import StateDep


router = APIRouter()


async def _check_ready(state: AppState) -> bool:
    checks = state.settings.cluster.readiness
    if checks.check_database:
        try:
            async with state.engine.connect():
                pass
        except Exception:
            return False
    return True


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "service": "upload-service"}


@router.get("/startupz")
async def startupz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    state: AppState = request.app.state.state
    ready = await _check_ready(state)
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready"},
    )


@router.get("/metrics")
async def metrics(state: StateDep) -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
