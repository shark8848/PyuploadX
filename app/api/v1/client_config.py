"""Portal client configuration per docs_product-design.md section 16.7."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header

from app.api.dependencies import SessionDep, StateDep
from app.core.errors import AuthenticationError

router = APIRouter(tags=["client-config"])


@router.get("/client-config")
async def client_config(
    state: StateDep,
    db: SessionDep,
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    settings = state.settings
    capabilities = state.storage.capabilities
    tenant_id = "default"
    if settings.auth.mode != "none" and x_api_key:
        try:
            tenant_id = state.authenticator.authenticate(x_api_key).tenant_id
        except AuthenticationError:
            tenant_id = "default"
    allowed_buckets = await state.bucket_service.list_buckets_for_tenant(db, tenant_id)
    managed_buckets = await state.bucket_service.list_managed_buckets_for_tenant(db, tenant_id)
    default_bucket = await state.setting_service.get_default_bucket(db)
    presign_default = await state.setting_service.get_presign_default_seconds(db)
    max_file_size = await state.setting_service.get_max_file_size(db)
    direct_threshold = await state.setting_service.get_direct_threshold(db)
    default_mode = await state.setting_service.get_default_mode(db)
    default_part_size = await state.setting_service.get_default_part_size(db)
    session_expiry = await state.setting_service.get_session_expiry(db)
    lifecycle_default = await state.setting_service.get_lifecycle_default(db)
    return {
        "service": {
            "name": settings.app.name,
            "version": settings.app.version,
        },
        "uploads": {
            "maximum_file_size_bytes": max_file_size,
            "default_mode": default_mode,
            "direct_upload_threshold_bytes": direct_threshold,
            "multipart": {
                "enabled": settings.uploads.multipart.enabled,
                "default_part_size_bytes": default_part_size,
                "minimum_part_size_bytes": settings.uploads.multipart.minimum_part_size_bytes,
                "maximum_part_size_bytes": settings.uploads.multipart.maximum_part_size_bytes,
                "maximum_parts": settings.uploads.multipart.maximum_parts,
                "maximum_presign_batch_size": settings.uploads.multipart.maximum_presign_batch_size,
            },
            "session": {
                "expires_after_seconds": session_expiry,
                "refresh_enabled": settings.uploads.session.refresh_enabled,
            },
            "allowed_buckets": allowed_buckets,
            "managed_buckets": managed_buckets,
            "default_bucket": default_bucket,
        },
        "presign": {
            "default_expires_seconds": presign_default,
            "maximum_expires_seconds": settings.presign.maximum_expires_seconds,
        },
        "storage": {
            "backend": state.storage.backend_name,
            "capabilities": {
                "multipart": capabilities.multipart,
                "presigned_put": capabilities.presigned_put,
                "presigned_get": capabilities.presigned_get,
                "presigned_upload_part": capabilities.presigned_upload_part,
                "list_parts": capabilities.list_parts,
            },
        },
        "lifecycle": {
            "enabled": settings.lifecycle.enabled,
            "allowed_modes": settings.lifecycle.policy.allowed_modes,
            "allowed_actions": settings.lifecycle.policy.allowed_actions,
            "permanent_allowed": settings.lifecycle.policy.permanent_allowed,
            "minimum_ttl_seconds": settings.lifecycle.policy.minimum_ttl_seconds,
            "maximum_ttl_seconds": settings.lifecycle.policy.maximum_ttl_seconds,
            "default_policy": lifecycle_default,
        },
        "directory_upload": {
            "enabled": settings.directory_upload.enabled,
            "limits": settings.directory_upload.limits.model_dump(),
            "default_file_concurrency": settings.directory_upload.upload["default_file_concurrency"],
            "maximum_file_concurrency": settings.directory_upload.upload["maximum_file_concurrency"],
            "default_part_concurrency": settings.directory_upload.upload["default_part_concurrency"],
            "maximum_part_concurrency": settings.directory_upload.upload["maximum_part_concurrency"],
            "maximum_total_concurrent_requests": settings.directory_upload.upload["maximum_total_concurrent_requests"],
            "conflicts": settings.directory_upload.conflicts.model_dump(),
            "symlinks": settings.directory_upload.symlinks.model_dump(),
            "ignore_defaults": settings.directory_upload.ignore.defaults,
            "ignore_file_name": settings.directory_upload.ignore.file_name,
        },
    }
