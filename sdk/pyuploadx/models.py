"""SDK data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FileInfo:
    id: str
    bucket: str
    object_key: str
    original_filename: str
    size_bytes: int
    content_type: str | None = None
    etag: str | None = None
    checksum_value: str | None = None
    status: str = "active"
    lifecycle_mode: str | None = None
    expires_at: str | None = None
    legal_hold: bool = False
    completed_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileInfo":
        return cls(
            id=data["id"],
            bucket=data["bucket"],
            object_key=data["object_key"],
            original_filename=data.get("original_filename", ""),
            size_bytes=data.get("size_bytes", 0),
            content_type=data.get("content_type"),
            etag=data.get("etag"),
            checksum_value=data.get("checksum_value"),
            status=data.get("status", "active"),
            lifecycle_mode=data.get("lifecycle_mode"),
            expires_at=data.get("expires_at"),
            legal_hold=data.get("legal_hold", False),
            completed_at=data.get("completed_at"),
        )


@dataclass
class UploadSessionInfo:
    id: str
    bucket: str
    object_key: str
    original_filename: str
    total_size: int
    part_size: int
    total_parts: int
    upload_mode: str
    backend: str
    storage_upload_id: str | None = None
    file_fingerprint: str | None = None
    expected_sha256: str | None = None
    status: str = "initiated"
    effective_lifecycle: dict[str, Any] | None = None
    completed_file_id: str | None = None
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UploadSessionInfo":
        return cls(
            id=data["id"],
            bucket=data["bucket"],
            object_key=data["object_key"],
            original_filename=data.get("original_filename", ""),
            total_size=data.get("total_size", 0),
            part_size=data.get("part_size", 0),
            total_parts=data.get("total_parts", 0),
            upload_mode=data.get("upload_mode", "automatic"),
            backend=data.get("backend", "local"),
            storage_upload_id=data.get("storage_upload_id"),
            file_fingerprint=data.get("file_fingerprint"),
            expected_sha256=data.get("expected_sha256"),
            status=data.get("status", "initiated"),
            effective_lifecycle=data.get("effective_lifecycle"),
            completed_file_id=data.get("completed_file_id"),
            expires_at=data.get("expires_at"),
        )


@dataclass(frozen=True)
class UploadedPart:
    part_number: int
    etag: str
    size_bytes: int
    checksum_sha256: str | None = None


@dataclass
class DirectoryJobInfo:
    id: str
    root_directory_name: str
    bucket: str
    destination_prefix: str
    status: str
    conflict_policy: str = "reject"
    total_entries: int = 0
    total_files: int = 0
    total_directories: int = 0
    total_bytes: int = 0
    uploaded_files: int = 0
    uploaded_bytes: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    manifest_hash: str | None = None
    effective_lifecycle: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectoryJobInfo":
        return cls(
            id=data["id"],
            root_directory_name=data.get("root_directory_name", ""),
            bucket=data.get("bucket", ""),
            destination_prefix=data.get("destination_prefix", ""),
            status=data.get("status", ""),
            conflict_policy=data.get("conflict_policy", "reject"),
            total_entries=data.get("total_entries", 0),
            total_files=data.get("total_files", 0),
            total_directories=data.get("total_directories", 0),
            total_bytes=data.get("total_bytes", 0),
            uploaded_files=data.get("uploaded_files", 0),
            uploaded_bytes=data.get("uploaded_bytes", 0),
            failed_files=data.get("failed_files", 0),
            skipped_files=data.get("skipped_files", 0),
            manifest_hash=data.get("manifest_hash"),
            effective_lifecycle=data.get("effective_lifecycle"),
        )
