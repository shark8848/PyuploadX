"""Storage adapter protocol per docs_product-design.md section 15.1."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import BinaryIO, Protocol, runtime_checkable

from app.storage.capabilities import StorageCapabilities


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_key: str
    size_bytes: int
    etag: str | None = None
    content_type: str | None = None


@dataclass
class ObjectStream:
    bucket: str
    object_key: str
    size_bytes: int
    content_type: str | None
    etag: str | None = None
    chunks: AsyncIterator[bytes] | None = None

    def __aiter__(self) -> AsyncIterator[bytes]:
        if self.chunks is None:
            raise RuntimeError("ObjectStream has no chunk source")
        return self.chunks


@dataclass(frozen=True)
class UploadedPart:
    part_number: int
    etag: str
    size_bytes: int
    checksum_sha256: str | None = None


@runtime_checkable
class StorageAdapter(Protocol):
    """Contract implemented by LocalStorageAdapter and S3StorageAdapter."""

    capabilities: StorageCapabilities
    backend_name: str

    async def create_bucket(
        self,
        bucket: str,
    ) -> None: ...

    async def bucket_exists(
        self,
        bucket: str,
    ) -> bool: ...

    async def put_object(
        self,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        content_type: str | None,
        size_bytes: int | None,
        checksum_sha256: str | None = None,
    ) -> StoredObject: ...

    async def get_object(
        self,
        bucket: str,
        object_key: str,
        *,
        offset: int = 0,
        length: int | None = None,
    ) -> ObjectStream: ...

    async def delete_object(
        self,
        bucket: str,
        object_key: str,
    ) -> None: ...

    async def object_exists(
        self,
        bucket: str,
        object_key: str,
    ) -> bool: ...

    async def initiate_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        content_type: str | None,
        metadata: dict[str, str],
    ) -> str: ...

    async def upload_part(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        part_number: int,
        stream: BinaryIO,
        size_bytes: int,
        checksum_sha256: str | None,
    ) -> UploadedPart: ...

    async def list_parts(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> list[UploadedPart]: ...

    async def complete_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        parts: list[UploadedPart],
    ) -> StoredObject: ...

    async def abort_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> None: ...

    async def create_presigned_put_url(
        self,
        bucket: str,
        object_key: str,
        expires_seconds: int,
        content_type: str | None = None,
    ) -> str: ...

    async def create_presigned_get_url(
        self,
        bucket: str,
        object_key: str,
        expires_seconds: int,
    ) -> str: ...

    async def create_presigned_upload_part_url(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        part_number: int,
        expires_seconds: int,
    ) -> str: ...
