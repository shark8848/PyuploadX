"""Local storage adapter contract tests (docs 15.3)."""

from __future__ import annotations

import io

import pytest

from app.core.errors import ApiError
from app.storage.local import LocalStorageAdapter, safe_join
from app.config.models import LocalStorageConfig


@pytest.fixture()
def adapter(tmp_path) -> LocalStorageAdapter:
    return LocalStorageAdapter(
        LocalStorageConfig(
            root_path=str(tmp_path / "storage"),
            multipart_path=str(tmp_path / "storage" / ".multipart"),
            fsync=False,
        )
    )


@pytest.mark.asyncio
async def test_put_get_delete(adapter):
    stored = await adapter.put_object(
        "app-default", "a/b.txt", io.BytesIO(b"hello world"), "text/plain", 11
    )
    assert stored.etag
    stream = await adapter.get_object("app-default", "a/b.txt")
    chunks = [chunk async for chunk in stream]
    assert b"".join(chunks) == b"hello world"
    assert stream.size_bytes == 11
    await adapter.delete_object("app-default", "a/b.txt")
    with pytest.raises(ApiError):
        await adapter.get_object("app-default", "a/b.txt")


@pytest.mark.asyncio
async def test_multipart_flow(adapter):
    upload_id = "test-multipart-1"
    await adapter.upload_part("b", "k", upload_id, 1, io.BytesIO(b"part1"), 5, None)
    await adapter.upload_part("b", "k", upload_id, 2, io.BytesIO(b"part22"), 6, None)
    parts = await adapter.list_parts("b", "k", upload_id)
    assert [p.part_number for p in parts] == [1, 2]
    stored = await adapter.complete_multipart_upload("b", "k", upload_id, parts)
    assert stored.size_bytes == 11
    stream = await adapter.get_object("b", "k")
    assert b"".join([chunk async for chunk in stream]) == b"part1part22"


def test_safe_join_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "..", "secret.txt")


@pytest.mark.asyncio
async def test_checksum_mismatch_raises(adapter):
    from app.core.errors import ChecksumMismatchError

    with pytest.raises(ChecksumMismatchError):
        await adapter.put_object(
            "b",
            "k",
            io.BytesIO(b"data"),
            None,
            4,
            checksum_sha256="0" * 64,
        )
