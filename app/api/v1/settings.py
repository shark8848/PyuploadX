"""Portal storage settings API backed by runtime overrides."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import IdentityDep, SessionDep, StateDep

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
) -> dict[str, Any]:
    effective = await state.setting_service.get_effective(db)
    return {
        "storage": {
            **effective,
            "maximum_expires_seconds": state.settings.presign.maximum_expires_seconds,
        }
    }


@router.put("")
async def update_settings(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    body: dict[str, Any],
) -> dict[str, Any]:
    allowed_buckets = await state.bucket_service.list_buckets_for_tenant(db, identity.tenant_id)
    effective = await state.setting_service.update(db, body, allowed_buckets)
    await db.commit()
    return {
        "storage": {
            **effective,
            "maximum_expires_seconds": state.settings.presign.maximum_expires_seconds,
        }
    }
