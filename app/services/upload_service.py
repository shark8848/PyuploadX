"""Upload session orchestration per docs_product-design.md section 11/12/16.4."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.models import Settings
from app.core import metrics
from app.core.auth import Identity
from app.core.errors import (
    ApiError,
    InvalidPartNumberError,
    InvalidPartSizeError,
    MissingPartsError,
    ObjectAlreadyExistsError,
    StorageCapabilityNotSupportedError,
    UploadAbortedError,
    UploadAlreadyCompletedError,
    UploadExpiredError,
    UploadNotFoundError,
    UploadStateConflictError,
)
from app.db import repositories
from app.db.models import (
    FileObject,
    FileStatus,
    LifecycleStatus,
    PartStatus,
    StorageBackend,
    UploadMode,
    UploadPart,
    UploadSession,
    UploadStatus,
)
from app.directory_upload.paths import normalize_relative_path
from app.lifecycle.policy import compute_effective_lifecycle
from app.lifecycle.state_machine import transition_upload
from app.storage.base import StorageAdapter
from app.storage.local import LocalStorageAdapter


def _now() -> datetime:
    return datetime.now(UTC)


def serialize_session(session: UploadSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "bucket": session.bucket,
        "object_key": session.object_key,
        "original_filename": session.original_filename,
        "content_type": session.content_type,
        "total_size": session.total_size,
        "part_size": session.part_size,
        "total_parts": session.total_parts,
        "upload_mode": session.upload_mode.value,
        "backend": session.backend.value,
        "storage_upload_id": session.storage_upload_id,
        "file_fingerprint": session.file_fingerprint,
        "expected_sha256": session.expected_sha256,
        "status": session.status.value,
        "requested_lifecycle": session.requested_lifecycle,
        "effective_lifecycle": session.effective_lifecycle,
        "completed_file_id": str(session.completed_file_id) if session.completed_file_id else None,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


class UploadService:
    def __init__(self, settings: Settings, storage: StorageAdapter, bucket_service, setting_service) -> None:
        self.settings = settings
        self.storage = storage
        self.bucket_service = bucket_service
        self.setting_service = setting_service

    def _validate_object_key(self, object_key: str) -> str:
        return normalize_relative_path(object_key, maximum_bytes=1024)

    async def _validate_bucket(self, session: AsyncSession, identity: Identity, bucket: str) -> None:
        if not await self.bucket_service.is_bucket_allowed(session, identity.tenant_id, bucket):
            raise ApiError(
                "INVALID_BUCKET",
                f"Bucket {bucket!r} is not allowed.",
                status_code=422,
                details={"allowed_buckets": self.settings.storage.allowed_buckets},
            )

    async def create_session(
        self,
        session: AsyncSession,
        identity: Identity,
        *,
        bucket: str,
        object_key: str,
        original_filename: str,
        content_type: str | None,
        total_size: int,
        part_size: int | None,
        upload_mode: str,
        file_fingerprint: str | None,
        expected_sha256: str | None,
        lifecycle: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> UploadSession:
        await self._validate_bucket(session, identity, bucket)
        safe_key = self._validate_object_key(object_key)
        maximum_bytes = await self.setting_service.get_max_file_size(session)
        if total_size < 0:
            raise ApiError("INVALID_FILE_SIZE", "total_size must be non-negative.", status_code=422)
        if total_size > maximum_bytes:
            raise ApiError(
                "FILE_TOO_LARGE",
                f"File size exceeds the maximum of {maximum_bytes} bytes.",
                status_code=422,
                details={"maximum_bytes": maximum_bytes},
            )

        multipart = self.settings.uploads.multipart
        if part_size is None:
            part_size = await self.setting_service.get_default_part_size(session)
        if not (multipart.minimum_part_size_bytes <= part_size <= multipart.maximum_part_size_bytes):
            raise InvalidPartSizeError(
                part_size, multipart.minimum_part_size_bytes, multipart.maximum_part_size_bytes
            )
        total_parts = max(1, math.ceil(total_size / part_size))
        if total_parts > multipart.maximum_parts:
            raise ApiError(
                "TOO_MANY_PARTS",
                f"File requires {total_parts} parts; maximum is {multipart.maximum_parts}.",
                status_code=422,
            )

        mode_value = upload_mode or await self.setting_service.get_default_mode(session)
        if mode_value == UploadMode.automatic.value:
            threshold = await self.setting_service.get_direct_threshold(session)
            use_multipart = multipart.enabled and total_size > threshold
            mode = UploadMode.presigned if use_multipart else UploadMode.proxy
        elif mode_value in (UploadMode.proxy.value, UploadMode.presigned.value):
            mode = UploadMode(mode_value)
            if mode == UploadMode.presigned and not self.storage.capabilities.multipart and total_size > 0:
                raise StorageCapabilityNotSupportedError("multipart")
        else:
            raise ApiError("INVALID_UPLOAD_MODE", f"Unknown upload mode: {upload_mode}", status_code=422)

        if self.settings.uploads.object_conflict_policy == "reject" and await self.storage.object_exists(
            bucket, safe_key
        ):
            raise ObjectAlreadyExistsError(bucket, safe_key)

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
            )

        backend = StorageBackend(self.settings.storage.backend)
        storage_upload_id: str | None = None
        if mode == UploadMode.presigned:
            storage_upload_id = await self.storage.initiate_multipart_upload(
                bucket=bucket,
                object_key=safe_key,
                content_type=content_type,
                metadata={"tenant_id": identity.tenant_id, "principal_id": identity.principal_id},
            )
            if isinstance(self.storage, LocalStorageAdapter):
                storage_upload_id = None

        now = _now()
        upload = UploadSession(
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            backend=backend,
            upload_mode=mode,
            bucket=bucket,
            object_key=safe_key,
            storage_upload_id=storage_upload_id,
            original_filename=original_filename or safe_key.rsplit("/", 1)[-1],
            content_type=content_type,
            total_size=total_size,
            part_size=part_size,
            total_parts=total_parts,
            file_fingerprint=file_fingerprint,
            expected_sha256=expected_sha256,
            status=UploadStatus.initiated,
            requested_lifecycle=lifecycle,
            effective_lifecycle=effective_lifecycle,
            version=1,
            expires_at=now + timedelta(seconds=await self.setting_service.get_session_expiry(session)),
            last_activity_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(upload)
        await session.flush()
        if isinstance(self.storage, LocalStorageAdapter):
            upload.storage_upload_id = str(upload.id)
        metrics.upload_active_sessions.inc()
        metrics.upload_requests_total.labels("initiate").inc()
        return upload

    async def get_session(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
    ) -> UploadSession:
        upload = await repositories.upload_repository.get_upload(
            session, upload_id, tenant_id=identity.tenant_id
        )
        if upload is None:
            raise UploadNotFoundError(str(upload_id))
        return upload

    async def list_committed_parts(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
    ) -> list[UploadPart]:
        await self.get_session(session, identity, upload_id)
        return await repositories.part_repository.list_parts_for_upload(session, upload_id)

    async def presign_parts(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
        part_numbers: list[int],
        expires_seconds: int | None = None,
    ) -> dict[int, str]:
        upload = await self.get_session(session, identity, upload_id)
        self._ensure_active(upload)
        if not self.storage.capabilities.presigned_upload_part or not upload.storage_upload_id:
            raise StorageCapabilityNotSupportedError("presigned_upload_part")
        batch_max = self.settings.uploads.multipart.maximum_presign_batch_size
        if len(part_numbers) > batch_max:
            raise ApiError(
                "PRESIGN_BATCH_TOO_LARGE",
                f"At most {batch_max} part URLs per request.",
                status_code=422,
                details={"maximum": batch_max},
            )
        expires = expires_seconds or self.settings.presign.upload_part_expires_seconds
        if expires > self.settings.presign.maximum_expires_seconds:
            expires = self.settings.presign.maximum_expires_seconds
        urls: dict[int, str] = {}
        for part_number in sorted(set(part_numbers)):
            if not (1 <= part_number <= upload.total_parts):
                raise InvalidPartNumberError(part_number, upload.total_parts)
            urls[part_number] = await self.storage.create_presigned_upload_part_url(
                bucket=upload.bucket,
                object_key=upload.object_key,
                storage_upload_id=upload.storage_upload_id,
                part_number=part_number,
                expires_seconds=expires,
            )
        return urls

    async def proxy_upload_part(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
        part_number: int,
        stream: BinaryIO,
        size_bytes: int,
        checksum_sha256: str | None,
    ) -> UploadPart:
        upload = await self.get_session(session, identity, upload_id)
        self._ensure_active(upload)
        if not (1 <= part_number <= upload.total_parts):
            raise InvalidPartNumberError(part_number, upload.total_parts)
        offset = (part_number - 1) * upload.part_size
        minimum = self.settings.uploads.multipart.minimum_part_size_bytes
        last_part = part_number == upload.total_parts
        if size_bytes > upload.part_size or (size_bytes < minimum and not last_part and upload.total_parts > 1):
            raise InvalidPartSizeError(size_bytes, minimum, upload.part_size)

        if upload.status == UploadStatus.initiated:
            await repositories.upload_repository.update_status(
                session, upload.id, UploadStatus.uploading
            )
            upload.status = UploadStatus.uploading

        stored = await self.storage.upload_part(
            bucket=upload.bucket,
            object_key=upload.object_key,
            storage_upload_id=upload.storage_upload_id or str(upload.id),
            part_number=part_number,
            stream=stream,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
        )
        await repositories.part_repository.upsert_part(
            session,
            upload_id=upload.id,
            part_number=part_number,
            offset_bytes=offset,
            size_bytes=stored.size_bytes,
            etag=stored.etag,
            checksum_sha256=stored.checksum_sha256 or checksum_sha256,
            status=PartStatus.committed,
        )
        metrics.upload_parts_total.inc()
        metrics.upload_part_bytes_total.inc(stored.size_bytes)
        await repositories.upload_repository.touch_activity(session, upload.id)
        await session.flush()
        return UploadPart(
            upload_id=upload.id,
            part_number=part_number,
            offset_bytes=offset,
            size_bytes=stored.size_bytes,
            etag=stored.etag,
            checksum_sha256=stored.checksum_sha256 or checksum_sha256,
            status=PartStatus.committed,
        )

    async def commit_part(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
        part_number: int,
        etag: str,
        size_bytes: int,
        checksum_sha256: str | None,
    ) -> None:
        upload = await self.get_session(session, identity, upload_id)
        self._ensure_active(upload)
        if not (1 <= part_number <= upload.total_parts):
            raise InvalidPartNumberError(part_number, upload.total_parts)
        offset = (part_number - 1) * upload.part_size
        await repositories.part_repository.upsert_part(
            session,
            upload_id=upload.id,
            part_number=part_number,
            offset_bytes=offset,
            size_bytes=size_bytes,
            etag=etag,
            checksum_sha256=checksum_sha256,
            status=PartStatus.committed,
        )
        metrics.upload_parts_total.inc()
        metrics.upload_part_bytes_total.inc(size_bytes)
        await repositories.upload_repository.touch_activity(session, upload.id)

    async def resume(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
    ) -> tuple[UploadSession, list[int]]:
        upload = await self.get_session(session, identity, upload_id)
        if upload.status in (UploadStatus.aborted, UploadStatus.expired):
            raise UploadAbortedError() if upload.status == UploadStatus.aborted else UploadExpiredError()
        committed = {
            part.part_number for part in await repositories.part_repository.list_parts_for_upload(
                session, upload.id
            )
            if part.status == PartStatus.committed
        }
        stored: set[int] = set()
        if upload.storage_upload_id and self.storage.capabilities.list_parts:
            try:
                stored_parts = await self.storage.list_parts(
                    bucket=upload.bucket,
                    object_key=upload.object_key,
                    storage_upload_id=upload.storage_upload_id,
                )
                stored = {part.part_number for part in stored_parts}
            except ApiError:
                stored = set()
        reconciled = committed | stored
        missing = [n for n in range(1, upload.total_parts + 1) if n not in reconciled]
        metrics.upload_resume_total.inc()
        await repositories.upload_repository.touch_activity(session, upload.id)
        return upload, missing

    async def complete(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
    ) -> FileObject:
        upload = await repositories.upload_repository.get_upload(
            session, upload_id, tenant_id=identity.tenant_id, for_update=True
        )
        if upload is None:
            raise UploadNotFoundError(str(upload_id))
        if upload.status == UploadStatus.completed:
            if upload.completed_file_id is not None:
                existing = await repositories.file_repository.get_file(
                    session, upload.completed_file_id, tenant_id=identity.tenant_id
                )
                if existing is not None:
                    return existing
        if upload.status == UploadStatus.aborted:
            raise UploadAbortedError()
        if upload.status == UploadStatus.expired:
            raise UploadExpiredError()

        committed = await repositories.part_repository.list_parts_for_upload(session, upload.id)
        committed_parts = [part for part in committed if part.status == PartStatus.committed]
        if len(committed_parts) < upload.total_parts:
            missing = sorted(
                {
                    n
                    for n in range(1, upload.total_parts + 1)
                    if n not in {part.part_number for part in committed_parts}
                }
            )
            raise MissingPartsError(missing)

        stored_parts = committed_parts
        if upload.storage_upload_id and self.storage.capabilities.list_parts:
            stored_parts = await self.storage.list_parts(
                bucket=upload.bucket,
                object_key=upload.object_key,
                storage_upload_id=upload.storage_upload_id,
            )
            if not stored_parts and isinstance(self.storage, LocalStorageAdapter):
                stored_parts = committed_parts
            committed_by_number = {part.part_number: part for part in committed_parts}
            for stored in stored_parts:
                db_part = committed_by_number.get(stored.part_number)
                if db_part and db_part.etag and stored.etag and db_part.etag != stored.etag:
                    raise ApiError(
                        "PART_ETAG_MISMATCH",
                        f"ETag for part {stored.part_number} does not match storage.",
                        status_code=409,
                        details={"part_number": stored.part_number},
                    )

        if upload.status not in (UploadStatus.uploading, UploadStatus.initiated):
            transition_upload(upload.status, UploadStatus.completing)
        upload.status = UploadStatus.completing
        await session.flush()

        stored = await self.storage.complete_multipart_upload(
            bucket=upload.bucket,
            object_key=upload.object_key,
            storage_upload_id=upload.storage_upload_id or str(upload.id),
            parts=[
                type("P", (), {"part_number": p.part_number, "etag": p.etag or "", "size_bytes": p.size_bytes})()
                for p in stored_parts
            ],
        )

        completed_at = _now()
        effective_lifecycle = upload.effective_lifecycle or {}
        expires_at: datetime | None = None
        next_action_at: datetime | None = None
        ttl_seconds: int | None = None
        mode = "permanent"
        if self.settings.lifecycle.enabled and effective_lifecycle:
            mode = effective_lifecycle.get("mode", "permanent")
            if effective_lifecycle.get("expires_at"):
                expires_at = datetime.fromisoformat(effective_lifecycle["expires_at"])
            ttl_seconds = effective_lifecycle.get("ttl_seconds")
            if effective_lifecycle.get("action") != "none" and expires_at is not None:
                next_action_at = expires_at

        file_obj = FileObject(
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            bucket=upload.bucket,
            object_key=upload.object_key,
            storage_backend=upload.backend,
            original_filename=upload.original_filename,
            size_bytes=upload.total_size,
            content_type=upload.content_type,
            etag=stored.etag,
            checksum_algorithm="sha256" if upload.expected_sha256 else None,
            checksum_value=upload.expected_sha256,
            file_fingerprint=upload.file_fingerprint,
            upload_id=upload.id,
            metadata_={},
            status=FileStatus.active,
            lifecycle_mode=mode,
            lifecycle_action=effective_lifecycle.get("action", "delete"),
            lifecycle_status=LifecycleStatus.active,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
            next_action_at=next_action_at,
            lifecycle_source="client" if upload.requested_lifecycle else "server",
            completed_at=completed_at,
            created_at=completed_at,
            updated_at=completed_at,
        )
        session.add(file_obj)
        await session.flush()

        upload.status = UploadStatus.completed
        upload.completed_file_id = file_obj.id
        upload.updated_at = _now()
        metrics.upload_complete_total.inc()
        metrics.upload_active_sessions.dec()
        await session.flush()
        return file_obj

    async def abort(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
    ) -> UploadSession:
        upload = await repositories.upload_repository.get_upload(
            session, upload_id, tenant_id=identity.tenant_id, for_update=True
        )
        if upload is None:
            raise UploadNotFoundError(str(upload_id))
        if upload.status == UploadStatus.completed:
            raise UploadAlreadyCompletedError()
        if upload.status in (UploadStatus.aborted, UploadStatus.expired):
            return upload
        transition_upload(upload.status, UploadStatus.aborting)
        upload.status = UploadStatus.aborting
        await session.flush()
        if upload.storage_upload_id:
            try:
                await self.storage.abort_multipart_upload(
                    bucket=upload.bucket,
                    object_key=upload.object_key,
                    storage_upload_id=upload.storage_upload_id,
                )
            except ApiError:
                pass
        upload.status = UploadStatus.aborted
        upload.updated_at = _now()
        metrics.upload_abort_total.inc()
        metrics.upload_active_sessions.dec()
        await session.flush()
        return upload

    async def refresh(
        self,
        session: AsyncSession,
        identity: Identity,
        upload_id: uuid.UUID,
    ) -> UploadSession:
        if not self.settings.uploads.session.refresh_enabled:
            raise ApiError("REFRESH_DISABLED", "Session refresh is disabled.", status_code=409)
        upload = await repositories.upload_repository.get_upload(
            session, upload_id, tenant_id=identity.tenant_id, for_update=True
        )
        if upload is None:
            raise UploadNotFoundError(str(upload_id))
        if upload.status in (UploadStatus.completed, UploadStatus.aborted, UploadStatus.expired):
            raise UploadStateConflictError("Cannot refresh a finished upload session.")
        now = _now()
        lifetime = await self.setting_service.get_session_expiry(session)
        if upload.created_at + timedelta(seconds=self.settings.uploads.session.maximum_lifetime_seconds) < now:
            raise UploadExpiredError()
        upload.expires_at = now + timedelta(seconds=lifetime)
        upload.last_activity_at = now
        await session.flush()
        return upload

    def _ensure_active(self, upload: UploadSession) -> None:
        if upload.status == UploadStatus.completed:
            raise UploadAlreadyCompletedError()
        if upload.status == UploadStatus.aborted:
            raise UploadAbortedError()
        if upload.status == UploadStatus.expired:
            raise UploadExpiredError()
