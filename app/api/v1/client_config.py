"""Portal client configuration per docs_product-design.md section 16.7."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import StateDep

router = APIRouter(tags=["client-config"])


@router.get("/client-config")
async def client_config(state: StateDep) -> dict[str, Any]:
    settings = state.settings
    capabilities = state.storage.capabilities
    return {
        "service": {
            "name": settings.app.name,
            "version": settings.app.version,
        },
        "uploads": {
            "maximum_file_size_bytes": settings.uploads.file_size.maximum_bytes,
            "default_mode": settings.uploads.default_mode,
            "direct_upload_threshold_bytes": settings.uploads.direct_upload_threshold_bytes,
            "multipart": {
                "enabled": settings.uploads.multipart.enabled,
                "default_part_size_bytes": settings.uploads.multipart.default_part_size_bytes,
                "minimum_part_size_bytes": settings.uploads.multipart.minimum_part_size_bytes,
                "maximum_part_size_bytes": settings.uploads.multipart.maximum_part_size_bytes,
                "maximum_parts": settings.uploads.multipart.maximum_parts,
                "maximum_presign_batch_size": settings.uploads.multipart.maximum_presign_batch_size,
            },
            "session": {
                "expires_after_seconds": settings.uploads.session.expires_after_seconds,
                "refresh_enabled": settings.uploads.session.refresh_enabled,
            },
            "allowed_buckets": settings.storage.allowed_buckets,
            "default_bucket": settings.storage.default_bucket,
        },
        "presign": {
            "default_expires_seconds": settings.presign.default_expires_seconds,
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
            "default_policy": settings.lifecycle.default_policy.model_dump(),
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
