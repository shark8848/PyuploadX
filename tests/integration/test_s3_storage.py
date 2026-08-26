"""S3/MinIO storage adapter integration tests (docs 15.4, 29.2).

Skipped unless a real S3-compatible endpoint is available. Configure with:

    UPLOAD_MINIO_TEST=1
    UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL=http://localhost:9000
    UPLOAD_STORAGE__S3__PUBLIC_ENDPOINT_URL=http://localhost:9000
    S3_ACCESS_KEY=minioadmin
    S3_SECRET_KEY=minioadmin
"""

from __future__ import annotations

import io
import os
import uuid

import httpx
import pytest

from app.config.models import S3StorageConfig
from app.core.errors import ApiError
from app.storage.s3 import S3StorageAdapter

pytestmark = pytest.mark.skipif(
    os.environ.get("UPLOAD_MINIO_TEST") != "1",
    reason="requires UPLOAD_MINIO_TEST=1 and a running S3/MinIO endpoint",
)

BUCKET = "app-default"


def _config() -> S3StorageConfig:
    return S3StorageConfig(
        internal_endpoint_url=os.environ["UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL"],
        public_endpoint_url=os.environ.get("UPLOAD_STORAGE__S3__PUBLIC_ENDPOINT_URL"),
        access_key=os.environ["S3_ACCESS_KEY"],
        secret_key=os.environ["S3_SECRET_KEY"],
    )


def _ensure_bucket(adapter: S3StorageAdapter) -> None:
    try:
        adapter._internal.head_bucket(Bucket=BUCKET)
    except Exception:
        adapter._internal.create_bucket(Bucket=BUCKET)


@pytest.fixture()
def adapter() -> S3StorageAdapter:
    adapter = S3StorageAdapter(_config())
    _ensure_bucket(adapter)
    return adapter


def _key(prefix: str) -> str:
    return f"contract/{prefix}-{uuid.uuid4().hex}.bin"


def test_capabilities(adapter: S3StorageAdapter) -> None:
    caps = adapter.capabilities
    assert caps.multipart
    assert caps.presigned_put
    assert caps.presigned_get
    assert caps.presigned_upload_part
    assert caps.list_parts
    assert not caps.server_side_checksum


@pytest.mark.asyncio
async def test_put_get_delete(adapter: S3StorageAdapter) -> None:
    key = _key("roundtrip")
    body = b"hello from minio"
    stored = await adapter.put_object(BUCKET, key, io.BytesIO(body), "text/plain", len(body))
    assert stored.etag

    stream = await adapter.get_object(BUCKET, key)
    chunks = [chunk async for chunk in stream]
    assert b"".join(chunks) == body
    assert stream.size_bytes == len(body)

    await adapter.delete_object(BUCKET, key)
    with pytest.raises(ApiError):
        await adapter.get_object(BUCKET, key)


@pytest.mark.asyncio
async def test_multipart_flow(adapter: S3StorageAdapter) -> None:
    key = _key("multipart")
    part1 = b"p" * (5 * 1024 * 1024)  # MinIO/S3: non-final parts must be >= 5 MiB
    part2 = b"tail"
    upload_id = await adapter.initiate_multipart_upload(BUCKET, key, "application/octet-stream", {})
    await adapter.upload_part(BUCKET, key, upload_id, 1, io.BytesIO(part1), len(part1), None)
    await adapter.upload_part(BUCKET, key, upload_id, 2, io.BytesIO(part2), len(part2), None)
    parts = await adapter.list_parts(BUCKET, key, upload_id)
    assert [p.part_number for p in parts] == [1, 2]

    stored = await adapter.complete_multipart_upload(BUCKET, key, upload_id, parts)
    assert stored.etag  # S3 does not return a size on CompleteMultipartUpload

    stream = await adapter.get_object(BUCKET, key)
    assert b"".join([chunk async for chunk in stream]) == part1 + part2


@pytest.mark.asyncio
async def test_abort_multipart(adapter: S3StorageAdapter) -> None:
    key = _key("abort")
    upload_id = await adapter.initiate_multipart_upload(BUCKET, key, "application/octet-stream", {})
    await adapter.upload_part(BUCKET, key, upload_id, 1, io.BytesIO(b"part1"), 5, None)
    await adapter.abort_multipart_upload(BUCKET, key, upload_id)
    with pytest.raises(ApiError):
        await adapter.get_object(BUCKET, key)


@pytest.mark.asyncio
async def test_presigned_put_get(adapter: S3StorageAdapter) -> None:
    key = _key("presign")
    body = b"presigned payload"
    put_url = await adapter.create_presigned_put_url(BUCKET, key, 300, "application/octet-stream")
    async with httpx.AsyncClient() as client:
        # The presigned URL signs the Content-Type header; it must be sent verbatim.
        response = await client.put(
            put_url, content=body, headers={"Content-Type": "application/octet-stream"}
        )
        assert response.status_code == 200, response.text

    get_url = await adapter.create_presigned_get_url(BUCKET, key, 300)
    async with httpx.AsyncClient() as client:
        response = await client.get(get_url)
        assert response.status_code == 200, response.text
        assert response.content == body
