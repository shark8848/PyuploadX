"""Standalone presign API per docs_product-design.md section 16.3."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import IdentityDep, SessionDep, StateDep


router = APIRouter(prefix="/presign", tags=["presign"])


@router.post("/put")
async def presign_put(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    body: dict[str, Any],
) -> dict[str, Any]:
    url = await state.file_service.presign_put(
        db,
        identity,
        bucket=body["bucket"],
        object_key=body["object_key"],
        content_type=body.get("content_type"),
        expires_seconds=body.get("expires_seconds"),
    )
    return {"url": url, "method": "PUT"}


@router.post("/get")
async def presign_get(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    body: dict[str, Any],
) -> dict[str, Any]:
    from app.directory_upload.paths import normalize_relative_path
    from app.core.errors import ApiError

    bucket = body["bucket"]
    if bucket not in state.settings.storage.allowed_buckets:
        raise ApiError("INVALID_BUCKET", f"Bucket {bucket!r} is not allowed.", status_code=422)
    object_key = normalize_relative_path(body["object_key"])
    expires = body.get("expires_seconds") or state.settings.presign.default_expires_seconds
    expires = min(expires, state.settings.presign.maximum_expires_seconds)
    url = await state.storage.create_presigned_get_url(bucket, object_key, expires)
    return {"url": url, "method": "GET"}
