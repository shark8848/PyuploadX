"""S3/MinIO storage adapter per docs_product-design.md section 15.4."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any, BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config.models import S3StorageConfig
from app.core.errors import (
    ApiError,
    StorageUnavailableError,
)
from app.storage.base import ObjectStream, StoredObject, UploadedPart
from app.storage.capabilities import StorageCapabilities


def _build_client(config: S3StorageConfig, public: bool = False) -> Any:
    endpoint = config.public_endpoint_url if public else config.internal_endpoint_url
    return boto3.client(
        "s3",
        endpoint_url=endpoint or None,
        region_name=config.region,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        use_ssl=config.use_ssl,
        verify=config.verify_ssl,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if config.force_path_style else "auto"},
            max_pool_connections=config.max_pool_connections,
        ),
    )


def _etag_of(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip('"')


@dataclass
class S3StorageAdapter:
    config: S3StorageConfig
    backend_name: str = "s3"
    capabilities: StorageCapabilities = StorageCapabilities(
        multipart=True,
        presigned_put=True,
        presigned_get=True,
        presigned_upload_part=True,
        list_parts=True,
        server_side_checksum=False,
        archive=False,
        transition=False,
        restore=False,
    )

    def __post_init__(self) -> None:
        self._internal = _build_client(self.config, public=False)
        self._public = _build_client(self.config, public=True)

    def _run(self, callable, *args: Any, **kwargs: Any) -> Any:
        return asyncio.to_thread(callable, *args, **kwargs)

    def _raise(self, exc: Exception) -> None:
        if isinstance(exc, ClientError):
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404"}:
                raise ApiError("FILE_NOT_FOUND", "Object does not exist.", status_code=404) from exc
            if code == "NoSuchUpload":
                raise ApiError(
                    "UPLOAD_NOT_FOUND", "Multipart upload does not exist.", status_code=404
                ) from exc
        raise StorageUnavailableError(f"s3 operation failed: {exc}") from exc

    async def put_object(
        self,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        content_type: str | None,
        size_bytes: int | None,
        checksum_sha256: str | None = None,
    ) -> StoredObject:
        digest = hashlib.sha256()
        while True:
            chunk = await asyncio.to_thread(stream.read, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        try:
            await self._run(stream.seek, 0)
            response = await self._run(
                self._internal.put_object,
                Bucket=bucket,
                Key=object_key,
                Body=stream,
                ContentType=content_type or "application/octet-stream",
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            self._raise(exc)
        if checksum_sha256 is not None and checksum_sha256 != digest.hexdigest():
            from app.core.errors import ChecksumMismatchError

            raise ChecksumMismatchError()
        return StoredObject(
            bucket=bucket,
            object_key=object_key,
            size_bytes=size_bytes or 0,
            etag=_etag_of(response.get("ETag")),
            content_type=content_type,
        )

    async def get_object(self, bucket: str, object_key: str) -> ObjectStream:
        try:
            response = await self._run(
                self._internal.get_object, Bucket=bucket, Key=object_key
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)
        body = response["Body"]
        size = int(response.get("ContentLength") or 0)

        async def chunks():
            while True:
                chunk = await asyncio.to_thread(body.read, 1024 * 1024)
                if not chunk:
                    break
                yield chunk

        return ObjectStream(
            bucket=bucket,
            object_key=object_key,
            size_bytes=size,
            content_type=response.get("ContentType"),
            etag=_etag_of(response.get("ETag")),
            chunks=chunks(),
        )

    async def delete_object(self, bucket: str, object_key: str) -> None:
        try:
            await self._run(self._internal.delete_object, Bucket=bucket, Key=object_key)
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)

    async def object_exists(self, bucket: str, object_key: str) -> bool:
        try:
            await self._run(self._internal.head_object, Bucket=bucket, Key=object_key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            self._raise(exc)
        except BotoCoreError as exc:
            self._raise(exc)
        return False

    async def initiate_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        content_type: str | None,
        metadata: dict[str, str],
    ) -> str:
        try:
            response = await self._run(
                self._internal.create_multipart_upload,
                Bucket=bucket,
                Key=object_key,
                ContentType=content_type or "application/octet-stream",
                Metadata={k: v for k, v in metadata.items() if len(v) <= 2000},
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)
        return response["UploadId"]

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
        try:
            response = await self._run(
                self._internal.upload_part,
                Bucket=bucket,
                Key=object_key,
                UploadId=storage_upload_id,
                PartNumber=part_number,
                Body=stream,
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)
        return UploadedPart(
            part_number=part_number,
            etag=_etag_of(response.get("ETag")) or "",
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
        )

    async def list_parts(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> list[UploadedPart]:
        parts: list[UploadedPart] = []
        marker = 0
        try:
            while True:
                response = await self._run(
                    self._internal.list_parts,
                    Bucket=bucket,
                    Key=object_key,
                    UploadId=storage_upload_id,
                    PartNumberMarker=marker,
                )
                for part in response.get("Parts", []):
                    parts.append(
                        UploadedPart(
                            part_number=int(part["PartNumber"]),
                            etag=_etag_of(part.get("ETag")) or "",
                            size_bytes=int(part.get("Size") or 0),
                        )
                    )
                if response.get("IsTruncated"):
                    marker = response.get("NextPartNumberMarker", marker)
                else:
                    break
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)
        return parts

    async def complete_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        parts: list[UploadedPart],
    ) -> StoredObject:
        payload = {
            "Parts": [
                {"PartNumber": part.part_number, "ETag": f'"{part.etag}"'}
                for part in sorted(parts, key=lambda p: p.part_number)
            ]
        }
        try:
            response = await self._run(
                self._internal.complete_multipart_upload,
                Bucket=bucket,
                Key=object_key,
                UploadId=storage_upload_id,
                MultipartUpload=payload,
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)
        return StoredObject(
            bucket=bucket,
            object_key=object_key,
            size_bytes=0,
            etag=_etag_of(response.get("ETag")),
        )

    async def abort_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> None:
        try:
            await self._run(
                self._internal.abort_multipart_upload,
                Bucket=bucket,
                Key=object_key,
                UploadId=storage_upload_id,
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)

    async def create_presigned_put_url(
        self,
        bucket: str,
        object_key: str,
        expires_seconds: int,
        content_type: str | None = None,
    ) -> str:
        params: dict[str, Any] = {"Bucket": bucket, "Key": object_key}
        if content_type:
            params["ContentType"] = content_type
        try:
            return await self._run(
                self._public.generate_presigned_url,
                "put_object",
                Params=params,
                ExpiresIn=expires_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)

    async def create_presigned_get_url(
        self,
        bucket: str,
        object_key: str,
        expires_seconds: int,
    ) -> str:
        try:
            return await self._run(
                self._public.generate_presigned_url,
                "get_object",
                Params={"Bucket": bucket, "Key": object_key},
                ExpiresIn=expires_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)

    async def create_presigned_upload_part_url(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        part_number: int,
        expires_seconds: int,
    ) -> str:
        try:
            return await self._run(
                self._public.generate_presigned_url,
                "upload_part",
                Params={
                    "Bucket": bucket,
                    "Key": object_key,
                    "UploadId": storage_upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=expires_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            self._raise(exc)
