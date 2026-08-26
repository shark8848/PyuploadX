"""Directory upload orchestration per docs_product-design.md sections 13 and 16.6."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.models import Settings
from app.core import metrics
from app.core.auth import Identity
from app.core.errors import (
    ApiError,
    DirectoryHasFailedEntriesError,
    DuplicateNormalizedPathError,
    InvalidRelativePathError,
    ManifestHashMismatchError,
    UploadStateConflictError,
)
from app.db import repositories
from app.db.models import (
    ConflictPolicy,
    DirectorySource,
    DirectoryUploadEntry,
    DirectoryUploadJob,
    DirectoryJobStatus,
    EntryStatus,
    EntryType,
)
from app.directory_upload import state_machine
from app.directory_upload.aggregation import aggregate_progress
from app.directory_upload.manifest import manifest_hash_from_entries
from app.directory_upload.paths import join_prefix, normalize_relative_path
from app.lifecycle.policy import compute_effective_lifecycle


def _now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_job(job: DirectoryUploadJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "root_directory_name": job.root_directory_name,
        "bucket": job.bucket,
        "destination_prefix": job.destination_prefix,
        "status": job.status.value,
        "conflict_policy": job.conflict_policy.value,
        "total_entries": job.total_entries,
        "total_files": job.total_files,
        "total_directories": job.total_directories,
        "total_bytes": job.total_bytes,
        "uploaded_files": job.uploaded_files,
        "uploaded_bytes": job.uploaded_bytes,
        "failed_files": job.failed_files,
        "skipped_files": job.skipped_files,
        "manifest_hash": job.manifest_hash,
        "requested_lifecycle": job.requested_lifecycle,
        "effective_lifecycle": job.effective_lifecycle,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def serialize_entry(entry: DirectoryUploadEntry) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "entry_type": entry.entry_type.value,
        "relative_path": entry.relative_path,
        "normalized_path": entry.normalized_path,
        "object_key": entry.object_key,
        "size_bytes": entry.size_bytes,
        "last_modified_ns": entry.last_modified_ns,
        "content_type": entry.content_type,
        "fingerprint": entry.fingerprint,
        "full_sha256": entry.full_sha256,
        "upload_id": str(entry.upload_id) if entry.upload_id else None,
        "file_id": str(entry.file_id) if entry.file_id else None,
        "status": entry.status.value,
        "error_code": entry.error_code,
        "error_message": entry.error_message,
    }


class DirectoryUploadService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_job(
        self,
        session: AsyncSession,
        identity: Identity,
        *,
        root_directory_name: str,
        bucket: str,
        destination_prefix: str,
        conflict_policy: str,
        source: str,
        requested_lifecycle: dict[str, Any] | None,
    ) -> DirectoryUploadJob:
        if not self.settings.directory_upload.enabled:
            raise ApiError("DIRECTORY_UPLOAD_DISABLED", "Directory upload is disabled.", status_code=409)
        if bucket not in self.settings.storage.allowed_buckets:
            raise ApiError("INVALID_BUCKET", f"Bucket {bucket!r} is not allowed.", status_code=422)
        policy_value = conflict_policy or self.settings.directory_upload.conflicts.default_policy
        if policy_value not in self.settings.directory_upload.conflicts.allowed_policies:
            raise ApiError("INVALID_CONFLICT_POLICY", f"Unknown conflict policy: {policy_value}", status_code=422)
        prefix = destination_prefix.strip("/") if destination_prefix else ""
        if prefix:
            normalize_relative_path(prefix, maximum_bytes=1024)

        effective_lifecycle: dict[str, Any] | None = None
        if self.settings.lifecycle.enabled:
            effective_lifecycle = compute_effective_lifecycle(
                requested=requested_lifecycle,
                server_default=self.settings.lifecycle.default_policy.model_dump(),
                allow_client_override=self.settings.lifecycle.policy.allow_client_override,
                permanent_allowed=self.settings.lifecycle.policy.permanent_allowed,
                minimum_ttl_seconds=self.settings.lifecycle.policy.minimum_ttl_seconds,
                maximum_ttl_seconds=self.settings.lifecycle.policy.maximum_ttl_seconds,
                allowed_modes=self.settings.lifecycle.policy.allowed_modes,
                allowed_actions=self.settings.lifecycle.policy.allowed_actions,
            )

        job = DirectoryUploadJob(
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            source=DirectorySource(source),
            root_directory_name=root_directory_name,
            bucket=bucket,
            destination_prefix=prefix,
            status=DirectoryJobStatus.created,
            conflict_policy=ConflictPolicy(policy_value),
            requested_lifecycle=requested_lifecycle,
            effective_lifecycle=effective_lifecycle,
            version=1,
            expires_at=_now() + timedelta(seconds=self.settings.uploads.session.expires_after_seconds),
        )
        session.add(job)
        await session.flush()
        metrics.directory_upload_jobs_total.inc()
        metrics.directory_upload_active_jobs.inc()
        return job

    async def _transition(
        self,
        job: DirectoryUploadJob,
        target: DirectoryJobStatus,
    ) -> None:
        state_machine.transition(job.status, target)
        job.status = target
        job.updated_at = _now()

    async def add_entries(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
        entries: list[dict[str, Any]],
    ) -> int:
        job = await repositories.directory_repository.get_job(session, job_id, tenant_id=identity.tenant_id)
        if job is None:
            raise ApiError("DIRECTORY_UPLOAD_NOT_FOUND", "Directory upload job does not exist.", status_code=404)
        if job.status not in (DirectoryJobStatus.created, DirectoryJobStatus.manifest_uploading):
            raise UploadStateConflictError("Entries can only be added before the manifest is finalized.")
        if job.status == DirectoryJobStatus.created:
            await self._transition(job, DirectoryJobStatus.manifest_uploading)

        limits = self.settings.directory_upload.limits
        max_entries = limits.maximum_entries_per_manifest_request
        if len(entries) > max_entries:
            raise ApiError(
                "TOO_MANY_ENTRIES",
                f"At most {max_entries} entries per request.",
                status_code=422,
            )

        existing = {
            row[0]
            for row in (
                await session.execute(
                    select(DirectoryUploadEntry.normalized_path).where(
                        DirectoryUploadEntry.directory_upload_id == job.id
                    )
                )
            ).all()
        }
        added = 0
        total_files = 0
        total_dirs = 0
        total_bytes = 0
        for raw in entries:
            entry_type = raw.get("entry_type", "file")
            relative_path = raw.get("relative_path", "")
            try:
                normalized = normalize_relative_path(
                    relative_path,
                    maximum_depth=limits.maximum_path_depth,
                    maximum_bytes=limits.maximum_relative_path_bytes,
                )
            except InvalidRelativePathError:
                raise
            if normalized in existing:
                raise DuplicateNormalizedPathError(normalized)
            existing.add(normalized)
            size_bytes = int(raw.get("size_bytes", 0))
            object_key = join_prefix(job.destination_prefix, normalized)
            session.add(
                DirectoryUploadEntry(
                    directory_upload_id=job.id,
                    entry_type=EntryType(entry_type),
                    relative_path=relative_path,
                    normalized_path=normalized,
                    object_key=object_key,
                    size_bytes=size_bytes,
                    last_modified_ns=raw.get("last_modified_ns"),
                    content_type=raw.get("content_type"),
                    fingerprint=raw.get("fingerprint"),
                    full_sha256=raw.get("full_sha256"),
                    requested_lifecycle=raw.get("lifecycle") or job.requested_lifecycle,
                    effective_lifecycle=job.effective_lifecycle,
                    status=EntryStatus.pending,
                )
            )
            added += 1
            if entry_type == "file":
                total_files += 1
                total_bytes += size_bytes
            else:
                total_dirs += 1
        job.total_files += total_files
        job.total_directories += total_dirs
        job.total_bytes += total_bytes
        job.total_entries += added
        await session.flush()
        metrics.directory_upload_entries_total.inc(added)
        metrics.directory_upload_bytes_total.inc(total_bytes)
        return added

    async def complete_manifest(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
        *,
        expected_hash: str | None,
        counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        job = await repositories.directory_repository.get_job(
            session, job_id, tenant_id=identity.tenant_id, for_update=True
        )
        if job is None:
            raise ApiError("DIRECTORY_UPLOAD_NOT_FOUND", "Directory upload job does not exist.", status_code=404)
        if job.status not in (DirectoryJobStatus.created, DirectoryJobStatus.manifest_uploading):
            raise UploadStateConflictError("Manifest has already been completed.")

        entries_result = await session.execute(
            select(DirectoryUploadEntry).where(DirectoryUploadEntry.directory_upload_id == job.id)
        )
        entries = list(entries_result.scalars().all())
        if not entries:
            raise ApiError("MANIFEST_INCOMPLETE", "Manifest contains no entries.", status_code=409)

        entry_dicts = [
            {
                "relative_path": entry.normalized_path,
                "size_bytes": entry.size_bytes,
                "fingerprint": entry.fingerprint,
            }
            for entry in entries
            if entry.entry_type == EntryType.file
        ]
        actual_hash = manifest_hash_from_entries(entry_dicts)
        if expected_hash and expected_hash != actual_hash:
            raise ManifestHashMismatchError(expected_hash, actual_hash)
        if counts:
            if counts.get("files") != job.total_files:
                raise ApiError("MANIFEST_INCOMPLETE", "Manifest file count does not match.", status_code=409)
            if counts.get("directories") != job.total_directories:
                raise ApiError("MANIFEST_INCOMPLETE", "Manifest directory count does not match.", status_code=409)
        job.manifest_hash = actual_hash
        await self._transition(job, DirectoryJobStatus.ready)
        await session.flush()
        return serialize_job(job)

    async def get_job(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
    ) -> DirectoryUploadJob:
        job = await repositories.directory_repository.get_job(session, job_id, tenant_id=identity.tenant_id)
        if job is None:
            raise ApiError("DIRECTORY_UPLOAD_NOT_FOUND", "Directory upload job does not exist.", status_code=404)
        return job

    async def list_entries(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[DirectoryUploadEntry], str | None]:
        await self.get_job(session, identity, job_id)
        limit = min(max(limit, 1), 1000)
        stmt = select(DirectoryUploadEntry).where(DirectoryUploadEntry.directory_upload_id == job_id)
        if cursor:
            stmt = stmt.where(DirectoryUploadEntry.normalized_path > cursor)
        stmt = stmt.order_by(DirectoryUploadEntry.normalized_path).limit(limit + 1)
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = rows[-1].normalized_path
        return rows, next_cursor

    async def initiate_entry(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> dict[str, Any]:
        entry = await session.get(DirectoryUploadEntry, entry_id)
        if entry is None or entry.directory_upload_id != job_id:
            raise ApiError("ENTRY_NOT_FOUND", "Directory entry does not exist.", status_code=404)
        job = await self.get_job(session, identity, job_id)
        if job.status == DirectoryJobStatus.created:
            await self._transition(job, DirectoryJobStatus.manifest_uploading)
        entry.status = EntryStatus.uploading
        entry.attempt_count += 1
        await session.flush()
        return serialize_entry(entry)

    async def mark_entry_result(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
        entry_id: uuid.UUID,
        *,
        status: EntryStatus,
        file_id: uuid.UUID | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        entry = await session.get(DirectoryUploadEntry, entry_id)
        if entry is None or entry.directory_upload_id != job_id:
            raise ApiError("ENTRY_NOT_FOUND", "Directory entry does not exist.", status_code=404)
        await self.get_job(session, identity, job_id)
        entry.status = status
        entry.file_id = file_id
        entry.error_code = error_code
        entry.error_message = error_message
        await aggregate_progress(session, job_id)
        await session.flush()
        return serialize_entry(entry)

    async def retry(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
    ) -> dict[str, Any]:
        job = await self.get_job(session, identity, job_id)
        if job.status in (DirectoryJobStatus.completed, DirectoryJobStatus.completed_with_errors, DirectoryJobStatus.cancelled):
            raise UploadStateConflictError("Job has already finished.")
        await self._transition(job, DirectoryJobStatus.uploading)
        await session.flush()
        return serialize_job(job)

    async def complete(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
    ) -> dict[str, Any]:
        job = await repositories.directory_repository.get_job(
            session, job_id, tenant_id=identity.tenant_id, for_update=True
        )
        if job is None:
            raise ApiError("DIRECTORY_UPLOAD_NOT_FOUND", "Directory upload job does not exist.", status_code=404)
        if job.status == DirectoryJobStatus.completed:
            return serialize_job(job)
        if job.status not in (DirectoryJobStatus.uploading, DirectoryJobStatus.ready, DirectoryJobStatus.paused):
            raise UploadStateConflictError("Job is not in an uploadable state.")
        failed = await repositories.directory_repository.count_entries_by_status(
            session, job.id, EntryStatus.failed
        )
        if failed:
            raise DirectoryHasFailedEntriesError(failed)
        await self._transition(job, DirectoryJobStatus.finalizing)
        await aggregate_progress(session, job.id)
        await self._transition(job, DirectoryJobStatus.completed)
        await session.flush()
        metrics.directory_upload_active_jobs.dec()
        return serialize_job(job)

    async def cancel(
        self,
        session: AsyncSession,
        identity: Identity,
        job_id: uuid.UUID,
    ) -> dict[str, Any]:
        job = await repositories.directory_repository.get_job(
            session, job_id, tenant_id=identity.tenant_id, for_update=True
        )
        if job is None:
            raise ApiError("DIRECTORY_UPLOAD_NOT_FOUND", "Directory upload job does not exist.", status_code=404)
        if job.status in (DirectoryJobStatus.completed, DirectoryJobStatus.completed_with_errors):
            raise UploadStateConflictError("Job has already completed.")
        if job.status != DirectoryJobStatus.cancelled:
            await self._transition(job, DirectoryJobStatus.cancelling)
        await self._transition(job, DirectoryJobStatus.cancelled)
        await session.flush()
        metrics.directory_upload_active_jobs.dec()
        return serialize_job(job)
