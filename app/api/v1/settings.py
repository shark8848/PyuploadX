"""Portal runtime settings API backed by app_settings overrides.

Storage backend connection parameters (backend type, S3 keys, endpoints)
are bootstrap config and are returned read-only; they are changed via
config/settings.yaml or environment variables followed by a restart.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import IdentityDep, SessionDep, StateDep

router = APIRouter(prefix="/settings", tags=["settings"])


def _storage_info(state: StateDep, allowed_buckets: list[str]) -> dict[str, Any]:
    settings = state.settings.storage
    info: dict[str, Any] = {
        "backend": state.storage.backend_name,
        "capabilities": {
            "multipart": state.storage.capabilities.multipart,
            "presigned_put": state.storage.capabilities.presigned_put,
            "presigned_get": state.storage.capabilities.presigned_get,
            "presigned_upload_part": state.storage.capabilities.presigned_upload_part,
            "list_parts": state.storage.capabilities.list_parts,
        },
        "allowed_buckets": allowed_buckets,
    }
    if state.storage.backend_name == "local":
        info["root_path"] = settings.local.root_path
        info["multipart_path"] = settings.local.multipart_path
    else:
        info["endpoint"] = settings.s3.internal_endpoint_url or settings.s3.public_endpoint_url
        info["public_endpoint"] = settings.s3.public_endpoint_url
        info["region"] = settings.s3.region
        info["access_key_configured"] = bool(settings.s3.access_key)
        info["force_path_style"] = settings.s3.force_path_style
    return info


@router.get("")
async def get_settings(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
) -> dict[str, Any]:
    effective = await state.setting_service.get_effective(db)
    allowed_buckets = await state.bucket_service.list_buckets_for_tenant(db, identity.tenant_id)
    effective["storage"]["info"] = _storage_info(state, allowed_buckets)
    return effective


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
    effective["storage"]["info"] = _storage_info(state, allowed_buckets)
    return effective
