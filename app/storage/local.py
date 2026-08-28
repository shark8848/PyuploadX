"""Local filesystem storage adapter per docs_product-design.md section 15.3."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import aiofiles

from app.config.models import LocalStorageConfig
from app.core.errors import (
    StorageCapabilityNotSupportedError,
    StorageUnavailableError,
)
from app.storage.base import ObjectStream, StoredObject, UploadedPart
from app.storage.capabilities import StorageCapabilities


def safe_join(root: Path, *parts: str) -> Path:
    """Join path parts and reject any traversal outside root."""
    candidate = root.joinpath(*parts)
    try:
        resolved_root = root.resolve()
        resolved = candidate.resolve()
    except OSError as exc:
        raise StorageUnavailableError(f"cannot resolve path: {exc}") from exc
    if resolved != resolved_root and not resolved.is_relative_to(resolved_root):
        raise ValueError("path escapes storage root")
    return candidate


@dataclass
class LocalStorageAdapter:
    config: LocalStorageConfig
    backend_name: str = "local"
    capabilities: StorageCapabilities = StorageCapabilities(
        multipart=True,
        presigned_put=False,
        presigned_get=False,
        presigned_upload_part=False,
        list_parts=True,
        server_side_checksum=True,
        archive=False,
        transition=False,
        restore=False,
    )

    def __post_init__(self) -> None:
        self.root = Path(self.config.root_path)
        self.multipart_root = Path(self.config.multipart_path)

    def _object_path(self, bucket: str, object_key: str) -> Path:
        return safe_join(self.root, bucket, *object_key.split("/"))

    def _part_path(self, upload_id: str, part_number: int) -> Path:
        parts_dir = safe_join(self.multipart_root, upload_id, "parts")
        return parts_dir / f"{part_number:08d}.part"

    async def put_object(
        self,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        content_type: str | None,
        size_bytes: int | None,
        checksum_sha256: str | None = None,
    ) -> StoredObject:
        destination = self._object_path(bucket, object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        digest = hashlib.sha256()
        written = 0
        try:
            async with aiofiles.open(temporary, "wb") as out:
                while True:
                    chunk = await asyncio.to_thread(stream.read, 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    written += len(chunk)
                    await out.write(chunk)
                if self.config.fsync:
                    await out.flush()
                    os.fsync(out.fileno())
            os.replace(temporary, destination)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageUnavailableError(f"local write failed: {exc}") from exc
        actual_size = written if size_bytes is None else size_bytes
        if checksum_sha256 is not None and checksum_sha256 != digest.hexdigest():
            os.remove(destination)
            from app.core.errors import ChecksumMismatchError

            raise ChecksumMismatchError()
        return StoredObject(
            bucket=bucket,
            object_key=object_key,
            size_bytes=actual_size,
            etag=digest.hexdigest(),
            content_type=content_type,
        )

    async def get_object(
        self,
        bucket: str,
        object_key: str,
        *,
        offset: int = 0,
        length: int | None = None,
    ) -> ObjectStream:
        path = self._object_path(bucket, object_key)
        if not path.exists():
            from app.core.errors import ApiError

            raise ApiError("FILE_NOT_FOUND", f"Object {bucket}/{object_key} does not exist.", status_code=404)
        size = path.stat().st_size

        async def chunks() -> AsyncIterator[bytes]:
            remaining = length
            async with aiofiles.open(path, "rb") as file:
                if offset:
                    await file.seek(offset)
                while remaining is None or remaining > 0:
                    read_size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
                    chunk = await file.read(read_size)
                    if not chunk:
                        break
                    if remaining is not None:
                        remaining -= len(chunk)
                    yield chunk

        return ObjectStream(
            bucket=bucket,
            object_key=object_key,
            size_bytes=size,
            content_type=None,
            chunks=chunks(),
        )

    async def delete_object(self, bucket: str, object_key: str) -> None:
        path = self._object_path(bucket, object_key)
        path.unlink(missing_ok=True)

    async def object_exists(self, bucket: str, object_key: str) -> bool:
        return self._object_path(bucket, object_key).exists()

    async def initiate_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        content_type: str | None,
        metadata: dict[str, str],
    ) -> str:
        return ""

    async def upload_part(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        part_number: int,
        stream: BinaryIO,
        size_bytes: int,
        checksum_sha256: str | None,
    ) -> UploadedPart:
        path = self._part_path(storage_upload_id, part_number)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        written = 0
        try:
            async with aiofiles.open(path, "wb") as out:
                while True:
                    chunk = await asyncio.to_thread(stream.read, 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    written += len(chunk)
                    await out.write(chunk)
                if self.config.fsync:
                    await out.flush()
                    os.fsync(out.fileno())
        except OSError as exc:
            path.unlink(missing_ok=True)
            raise StorageUnavailableError(f"local part write failed: {exc}") from exc
        if written != size_bytes:
            path.unlink(missing_ok=True)
            raise ValueError(f"part size mismatch: expected {size_bytes}, wrote {written}")
        return UploadedPart(
            part_number=part_number,
            etag=digest.hexdigest(),
            size_bytes=written,
            checksum_sha256=digest.hexdigest(),
        )

    async def list_parts(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> list[UploadedPart]:
        parts_dir = safe_join(self.multipart_root, storage_upload_id, "parts")
        if not parts_dir.exists():
            return []
        result: list[UploadedPart] = []
        for part_path in sorted(parts_dir.glob("*.part")):
            result.append(
                UploadedPart(
                    part_number=int(part_path.stem),
                    etag="",
                    size_bytes=part_path.stat().st_size,
                )
            )
        return result

    async def complete_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        parts: list[UploadedPart],
    ) -> StoredObject:
        destination = self._object_path(bucket, object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        parts_dir = safe_join(self.multipart_root, storage_upload_id, "parts")
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        digest = hashlib.sha256()
        total = 0
        try:
            async with aiofiles.open(temporary, "wb") as out:
                for part in sorted(parts, key=lambda p: p.part_number):
                    part_path = parts_dir / f"{part.part_number:08d}.part"
                    if not part_path.exists():
                        raise FileNotFoundError(f"part file missing: {part_path}")
                    async with aiofiles.open(part_path, "rb") as part_file:
                        while True:
                            chunk = await part_file.read(1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                            total += len(chunk)
                            await out.write(chunk)
                if self.config.fsync:
                    await out.flush()
                    os.fsync(out.fileno())
            os.replace(temporary, destination)
        finally:
            shutil.rmtree(safe_join(self.multipart_root, storage_upload_id), ignore_errors=True)
        return StoredObject(
            bucket=bucket,
            object_key=object_key,
            size_bytes=total,
            etag=digest.hexdigest(),
        )

    async def abort_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> None:
        shutil.rmtree(safe_join(self.multipart_root, storage_upload_id), ignore_errors=True)

    async def create_presigned_put_url(
        self,
        bucket: str,
        object_key: str,
        expires_seconds: int,
        content_type: str | None = None,
    ) -> str:
        raise StorageCapabilityNotSupportedError("presigned_put")

    async def create_presigned_get_url(
        self,
        bucket: str,
        object_key: str,
        expires_seconds: int,
    ) -> str:
        raise StorageCapabilityNotSupportedError("presigned_get")

    async def create_presigned_upload_part_url(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        part_number: int,
        expires_seconds: int,
    ) -> str:
        raise StorageCapabilityNotSupportedError("presigned_upload_part")
