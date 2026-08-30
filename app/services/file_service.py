"""File object service per docs_product-design.md section 16.2."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.models import Settings
from app.core.auth import Identity
from app.core.errors import (
    ApiError,
    FileUnderLegalHoldError,
    ObjectAlreadyExistsError,
    StorageCapabilityNotSupportedError,
)
from app.core.ranges import ByteRange, parse_byte_range
from app.db import repositories
from app.db.models import FileObject, FileStatus, LifecycleStatus
from app.directory_upload.paths import normalize_relative_path
from app.core.permanent_links import sign, verify
from app.lifecycle.policy import compute_effective_lifecycle
from app.storage.base import StorageAdapter

logger = logging.getLogger("upload_service.service")


def _now() -> datetime:
    return datetime.now(UTC)


def serialize_file(file_obj: FileObject) -> dict[str, Any]:
    return {
        "id": str(file_obj.id),
        "bucket": file_obj.bucket,
        "object_key": file_obj.object_key,
        "original_filename": file_obj.original_filename,
        "content_type": file_obj.content_type,
        "size_bytes": file_obj.size_bytes,
        "etag": file_obj.etag,
        "checksum_algorithm": file_obj.checksum_algorithm,
        "checksum_value": file_obj.checksum_value,
        "file_fingerprint": file_obj.file_fingerprint,
        "upload_id": str(file_obj.upload_id) if file_obj.upload_id else None,
        "status": file_obj.status.value,
        "lifecycle_mode": file_obj.lifecycle_mode,
        "lifecycle_action": file_obj.lifecycle_action,
        "lifecycle_status": file_obj.lifecycle_status.value,
        "expires_at": file_obj.expires_at.isoformat() if file_obj.expires_at else None,
        "legal_hold": file_obj.legal_hold,
        "retention_until": file_obj.retention_until.isoformat() if file_obj.retention_until else None,
        "completed_at": file_obj.completed_at.isoformat() if file_obj.completed_at else None,
        "created_at": file_obj.created_at.isoformat() if file_obj.created_at else None,
    }


class FileService:
    def __init__(self, settings: Settings, storage: StorageAdapter, bucket_service, setting_service) -> None:
        self.settings = settings
        self.storage = storage
        self.bucket_service = bucket_service
        self.setting_service = setting_service

    async def proxy_upload(
        self,
        session: AsyncSession,
        identity: Identity,
        *,
        bucket: str,
        object_key: str,
        original_filename: str,
        content_type: str | None,
        size_bytes: int,
        stream: BinaryIO,
        checksum_sha256: str | None,
        file_fingerprint: str | None,
        lifecycle: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> FileObject:
        if not await self.bucket_service.is_bucket_allowed(session, identity.tenant_id, bucket):
            raise ApiError(
                "INVALID_BUCKET",
                f"Bucket {bucket!r} is not allowed.",
                status_code=422,
            )
        safe_key = normalize_relative_path(object_key, maximum_bytes=1024)
        if size_bytes > await self.setting_service.get_max_file_size(session):
            raise ApiError(
                "FILE_TOO_LARGE",
                f"File size exceeds the maximum of {self.settings.uploads.file_size.maximum_bytes} bytes.",
                status_code=422,
            )
        if self.settings.uploads.object_conflict_policy == "reject" and await self.storage.object_exists(
            bucket, safe_key
        ):
            raise ObjectAlreadyExistsError(bucket, safe_key)

        completed_at = _now()
        effective_lifecycle: dict[str, Any] | None = None
        if self.settings.lifecycle.enabled:
            effective_lifecycle = compute_effective_lifecycle(
                requested=lifecycle,
                server_default=await self.setting_service.get_lifecycle_default(session),
                allow_client_override=self.settings.lifecycle.policy.allow_client_override,
                permanent_allowed=self.settings.lifecycle.policy.permanent_allowed,
                minimum_ttl_seconds=self.settings.lifecycle.policy.minimum_ttl_seconds,
                maximum_ttl_seconds=self.settings.lifecycle.policy.maximum_ttl_seconds,
                allowed_modes=self.settings.lifecycle.policy.allowed_modes,
                allowed_actions=self.settings.lifecycle.policy.allowed_actions,
                completed_at=completed_at,
            )

        stored = await self.storage.put_object(
            bucket=bucket,
            object_key=safe_key,
            stream=stream,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
        )

        expires_at = None
        next_action_at = None
        ttl_seconds = None
        mode = "permanent"
        if effective_lifecycle:
            mode = effective_lifecycle.get("mode", "permanent")
            if effective_lifecycle.get("expires_at"):
                expires_at = datetime.fromisoformat(effective_lifecycle["expires_at"])
            ttl_seconds = effective_lifecycle.get("ttl_seconds")
            if effective_lifecycle.get("action") != "none" and expires_at is not None:
                next_action_at = expires_at

        file_obj = FileObject(
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            bucket=bucket,
            object_key=safe_key,
            storage_backend=self.storage.backend_name,
            original_filename=original_filename or safe_key.rsplit("/", 1)[-1],
            size_bytes=stored.size_bytes,
            content_type=content_type,
            etag=stored.etag,
            checksum_algorithm="sha256" if checksum_sha256 else None,
            checksum_value=checksum_sha256,
            file_fingerprint=file_fingerprint,
            metadata_=metadata or {},
            status=FileStatus.active,
            lifecycle_mode=mode,
            lifecycle_action=effective_lifecycle.get("action", "delete") if effective_lifecycle else "delete",
            lifecycle_status=LifecycleStatus.active,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
            next_action_at=next_action_at,
            lifecycle_source="client" if lifecycle else "server",
            completed_at=completed_at,
            created_at=completed_at,
            updated_at=completed_at,
        )
        session.add(file_obj)
        await session.flush()
        logger.info(
            "upload completed",
            extra={
                "extra_fields": {
                    "tenant_id": identity.tenant_id,
                    "principal_id": identity.principal_id,
                    "file_id": str(file_obj.id),
                    "bucket": file_obj.bucket,
                    "object_key": file_obj.object_key,
                    "original_filename": file_obj.original_filename,
                    "size_bytes": file_obj.size_bytes,
                    "backend": file_obj.storage_backend,
                }
            },
        )
        return file_obj

    async def get(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
    ) -> FileObject:
        file_obj = await repositories.file_repository.get_file(session, file_id, tenant_id=identity.tenant_id)
        if file_obj is None:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        if file_obj.status == FileStatus.deleted:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        return file_obj

    async def download(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
        *,
        range_header: str | None = None,
    ) -> tuple[Any, Any, ByteRange | None]:
        file_obj = await self.get(session, identity, file_id)
        byte_range = parse_byte_range(range_header, file_obj.size_bytes) if range_header else None
        offset = byte_range.start if byte_range else 0
        length = byte_range.length if byte_range else None
        stream = await self.storage.get_object(
            bucket=file_obj.bucket,
            object_key=file_obj.object_key,
            offset=offset,
            length=length,
        )
        return file_obj, stream, byte_range

    async def create_permanent_link(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
        base_url: str,
    ) -> str:
        """Return a permanent (non-expiring) download link for the file.

        The link is an HMAC-signed URL served by the API itself, so it works for
        every storage backend (Local included). It stays valid while the file
        exists; revoke by rotating UPLOAD_PERMANENT_LINK_SECRET or deleting the file.
        """
        if not self.settings.permanent_link.enabled:
            raise ApiError("PERMANENT_LINK_DISABLED", "Permanent links are disabled.", status_code=501)
        secret = self.settings.permanent_link.secret
        if not secret:
            raise ApiError(
                "PERMANENT_LINK_NOT_CONFIGURED",
                "Set UPLOAD_PERMANENT_LINK_SECRET to enable permanent links.",
                status_code=501,
            )
        await self.get(session, identity, file_id)
        token = sign(file_id, secret)
        return f"{base_url.rstrip('/')}/v1/files/{file_id}/download-link?token={token}"

    def verify_link_token(self, file_id: uuid.UUID, token: str) -> bool:
        secret = self.settings.permanent_link.secret
        if not secret:
            return False
        return verify(file_id, secret, token)

    async def download_for_link(
        self,
        session: AsyncSession,
        file_id: uuid.UUID,
        *,
        range_header: str | None = None,
    ) -> tuple[Any, Any, ByteRange | None]:
        """Stream a file through a verified permanent link (no tenant scope)."""
        file_obj = await repositories.file_repository.get_file(session, file_id)
        if file_obj is None or file_obj.status == FileStatus.deleted:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        byte_range = parse_byte_range(range_header, file_obj.size_bytes) if range_header else None
        offset = byte_range.start if byte_range else 0
        length = byte_range.length if byte_range else None
        stream = await self.storage.get_object(
            bucket=file_obj.bucket,
            object_key=file_obj.object_key,
            offset=offset,
            length=length,
        )
        return file_obj, stream, byte_range

    async def delete(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
    ) -> None:
        file_obj = await repositories.file_repository.get_file(
            session, file_id, tenant_id=identity.tenant_id, for_update=True
        )
        if file_obj is None or file_obj.status == FileStatus.deleted:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        if file_obj.legal_hold:
            raise FileUnderLegalHoldError()
        await self.storage.delete_object(bucket=file_obj.bucket, object_key=file_obj.object_key)
        file_obj.status = FileStatus.deleted
        file_obj.deleted_at = _now()
        file_obj.lifecycle_status = LifecycleStatus.deleted
        await session.flush()
        logger.info(
            "file deleted",
            extra={
                "extra_fields": {
                    "tenant_id": identity.tenant_id,
                    "principal_id": identity.principal_id,
                    "file_id": str(file_obj.id),
                    "bucket": file_obj.bucket,
                    "object_key": file_obj.object_key,
                    "original_filename": file_obj.original_filename,
                }
            },
        )

    async def presign_download(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
        expires_seconds: int | None,
    ) -> str:
        file_obj = await self.get(session, identity, file_id)
        if not self.storage.capabilities.presigned_get:
            raise StorageCapabilityNotSupportedError("presigned_get")
        expires = expires_seconds or self.settings.presign.default_expires_seconds
        expires = min(expires, self.settings.presign.maximum_expires_seconds)
        return await self.storage.create_presigned_get_url(
            bucket=file_obj.bucket,
            object_key=file_obj.object_key,
            expires_seconds=expires,
        )

    async def serialize_upload_result(
        self,
        session: AsyncSession,
        identity: Identity,
        file_obj: FileObject,
    ) -> dict[str, Any]:
        """FileInfo response extended with a temporary presigned download URL.

        Backends without presigned_get (e.g. Local) return download_url=None;
        clients then fall back to the proxied GET /v1/files/{id}/download.
        """
        data = serialize_file(file_obj)
        if self.storage.capabilities.presigned_get:
            try:
                expires = min(
                    self.settings.presign.default_expires_seconds,
                    self.settings.presign.maximum_expires_seconds,
                )
                data["download_url"] = await self.storage.create_presigned_get_url(
                    bucket=file_obj.bucket,
                    object_key=file_obj.object_key,
                    expires_seconds=expires,
                )
                data["expires_in"] = expires
            except StorageCapabilityNotSupportedError:
                data["download_url"] = None
                data["expires_in"] = None
        else:
            data["download_url"] = None
            data["expires_in"] = None
        return data

    async def presign_put(
        self,
        session: AsyncSession,
        identity: Identity,
        *,
        bucket: str,
        object_key: str,
        content_type: str | None,
        expires_seconds: int | None,
    ) -> str:
        if not await self.bucket_service.is_bucket_allowed(session, identity.tenant_id, bucket):
            raise ApiError("INVALID_BUCKET", f"Bucket {bucket!r} is not allowed.", status_code=422)
        safe_key = normalize_relative_path(object_key, maximum_bytes=1024)
        if not self.storage.capabilities.presigned_put:
            raise StorageCapabilityNotSupportedError("presigned_put")
        expires = expires_seconds or self.settings.presign.default_expires_seconds
        expires = min(expires, self.settings.presign.maximum_expires_seconds)
        return await self.storage.create_presigned_put_url(
            bucket=bucket,
            object_key=safe_key,
            expires_seconds=expires,
            content_type=content_type,
        )
