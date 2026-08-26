"""SQLAlchemy models for all tables defined in docs_product-design.md section 10."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    BigInteger as _BigInteger,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def enum_col(enum_type: type[Enum], length: int = 32) -> SAEnum:
    """Portable enum column: stored as VARCHAR, roundtrips as Python enum."""
    return SAEnum(enum_type, native_enum=False, length=length, validate_strings=False)


class StorageBackend(str, Enum):
    local = "local"
    s3 = "s3"


class UploadMode(str, Enum):
    automatic = "automatic"
    proxy = "proxy"
    presigned = "presigned"


class UploadStatus(str, Enum):
    initiated = "initiated"
    uploading = "uploading"
    completing = "completing"
    completed = "completed"
    aborting = "aborting"
    aborted = "aborted"
    expired = "expired"


class PartStatus(str, Enum):
    pending = "pending"
    uploaded = "uploaded"
    committed = "committed"
    failed = "failed"


class FileStatus(str, Enum):
    active = "active"
    deleted = "deleted"


class LifecycleMode(str, Enum):
    permanent = "permanent"
    ttl = "ttl"
    expires_at = "expires_at"
    temporary = "temporary"
    sliding_ttl = "sliding_ttl"


class LifecycleAction(str, Enum):
    delete = "delete"
    notify = "notify"
    none = "none"


class LifecycleStatus(str, Enum):
    active = "active"
    expiring = "expiring"
    expired = "expired"
    deleting = "deleting"
    deleted = "deleted"
    archiving = "archiving"
    archived = "archived"
    restoring = "restoring"


class DirectorySource(str, Enum):
    sdk = "sdk"
    portal = "portal"


class DirectoryJobStatus(str, Enum):
    created = "created"
    manifest_uploading = "manifest_uploading"
    ready = "ready"
    uploading = "uploading"
    paused = "paused"
    finalizing = "finalizing"
    completed = "completed"
    cancelling = "cancelling"
    cancelled = "cancelled"
    completed_with_errors = "completed_with_errors"


class EntryType(str, Enum):
    file = "file"
    directory = "directory"


class EntryStatus(str, Enum):
    pending = "pending"
    uploading = "uploading"
    uploaded = "uploaded"
    skipped = "skipped"
    failed = "failed"


class ConflictPolicy(str, Enum):
    reject = "reject"
    skip = "skip"
    overwrite = "overwrite"
    rename = "rename"
    compare = "compare"


class WebhookStatus(str, Enum):
    pending = "pending"
    delivered = "delivered"
    failed = "failed"


class FileObject(Base):
    __tablename__ = "file_objects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "bucket", "object_key", name="uq_file_objects_tenant_bucket_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    principal_id: Mapped[str] = mapped_column(String(128))
    bucket: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(1024))
    storage_backend: Mapped[StorageBackend] = mapped_column(enum_col(StorageBackend, 16))
    original_filename: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum_algorithm: Mapped[str | None] = mapped_column(String(32), nullable=True)
    checksum_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    upload_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    status: Mapped[FileStatus] = mapped_column(enum_col(FileStatus, 16), default=FileStatus.active)
    lifecycle_mode: Mapped[LifecycleMode] = mapped_column(enum_col(LifecycleMode), default=LifecycleMode.permanent)
    lifecycle_action: Mapped[LifecycleAction] = mapped_column(enum_col(LifecycleAction, 16), default=LifecycleAction.delete)
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(enum_col(LifecycleStatus), default=LifecycleStatus.active)
    ttl_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_source: Mapped[str] = mapped_column(String(64), default="client")
    delete_attempts: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    principal_id: Mapped[str] = mapped_column(String(128))
    backend: Mapped[StorageBackend] = mapped_column(enum_col(StorageBackend, 16))
    upload_mode: Mapped[UploadMode] = mapped_column(enum_col(UploadMode, 16))
    bucket: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(1024))
    storage_upload_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_size: Mapped[int] = mapped_column(BigInteger)
    part_size: Mapped[int] = mapped_column(BigInteger)
    total_parts: Mapped[int] = mapped_column(Integer)
    file_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[UploadStatus] = mapped_column(enum_col(UploadStatus, 16), default=UploadStatus.initiated, index=True)
    requested_lifecycle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    effective_lifecycle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    completed_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class UploadPart(Base):
    __tablename__ = "upload_parts"
    __table_args__ = (
        UniqueConstraint("upload_id", "part_number", name="uq_upload_parts_upload_part"),
    )

    id: Mapped[int] = mapped_column(
        _BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("upload_sessions.id", ondelete="CASCADE"), index=True
    )
    part_number: Mapped[int] = mapped_column(Integer)
    offset_bytes: Mapped[int] = mapped_column(BigInteger)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[PartStatus] = mapped_column(enum_col(PartStatus, 16), default=PartStatus.pending)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

class DirectoryUploadJob(Base):
    __tablename__ = "directory_upload_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    principal_id: Mapped[str] = mapped_column(String(128))
    source: Mapped[DirectorySource] = mapped_column(enum_col(DirectorySource, 16), default=DirectorySource.sdk)
    root_directory_name: Mapped[str] = mapped_column(String(1024))
    bucket: Mapped[str] = mapped_column(String(255))
    destination_prefix: Mapped[str] = mapped_column(String(1024))
    status: Mapped[DirectoryJobStatus] = mapped_column(enum_col(DirectoryJobStatus), default=DirectoryJobStatus.created, index=True)
    conflict_policy: Mapped[ConflictPolicy] = mapped_column(enum_col(ConflictPolicy, 16), default=ConflictPolicy.reject)
    total_entries: Mapped[int] = mapped_column(BigInteger, default=0)
    total_files: Mapped[int] = mapped_column(BigInteger, default=0)
    total_directories: Mapped[int] = mapped_column(BigInteger, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    uploaded_files: Mapped[int] = mapped_column(BigInteger, default=0)
    uploaded_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    failed_files: Mapped[int] = mapped_column(BigInteger, default=0)
    skipped_files: Mapped[int] = mapped_column(BigInteger, default=0)
    manifest_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_lifecycle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    effective_lifecycle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DirectoryUploadEntry(Base):
    __tablename__ = "directory_upload_entries"
    __table_args__ = (
        UniqueConstraint(
            "directory_upload_id", "normalized_path", name="uq_dir_entries_job_normalized_path"
        ),
        UniqueConstraint(
            "directory_upload_id", "object_key", name="uq_dir_entries_job_object_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    directory_upload_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("directory_upload_jobs.id", ondelete="CASCADE"), index=True
    )
    entry_type: Mapped[EntryType] = mapped_column(enum_col(EntryType, 16))
    relative_path: Mapped[str] = mapped_column(String(1024))
    normalized_path: Mapped[str] = mapped_column(String(1024))
    object_key: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    last_modified_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    upload_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[EntryStatus] = mapped_column(enum_col(EntryStatus, 16), default=EntryStatus.pending)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_lifecycle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    effective_lifecycle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

class LifecycleEvent(Base):
    __tablename__ = "lifecycle_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    directory_upload_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "operation", "idempotency_key", name="uq_idempotency_tenant_op_key"
        ),
    )

    id: Mapped[int] = mapped_column(
        _BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    operation: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(128))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class WebhookOutboxMessage(Base):
    __tablename__ = "webhook_outbox"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[WebhookStatus] = mapped_column(enum_col(WebhookStatus, 16), default=WebhookStatus.pending, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
