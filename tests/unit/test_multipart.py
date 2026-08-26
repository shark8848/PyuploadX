"""SDK multipart part-selection tests (docs 12.2, DoD: 只重传缺失分片)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from sdk.pyuploadx.multipart import upload_all_parts


def _part_response(part_number: int) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=200,
        json=lambda: {
            "part_number": part_number,
            "etag": f"etag-{part_number}",
            "size_bytes": 10,
            "checksum_sha256": None,
        },
    )


def test_upload_all_parts_uploads_everything_by_default() -> None:
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(b"0123456789" * 3)
        handle.flush()
        calls: list[str] = []

        def http_post(path: str, **kwargs):
            calls.append(path)
            return _part_response(int(path.rsplit("/", 1)[-1]))

        upload_all_parts(
            http_post=http_post,
            session=SimpleNamespace(id="s1", total_size=30, part_size=10, total_parts=3),
            file_path=Path(handle.name),
            part_size=10,
            total_parts=3,
            concurrency=1,
        )

    assert calls == ["/v1/uploads/s1/parts/1", "/v1/uploads/s1/parts/2", "/v1/uploads/s1/parts/3"]


def test_upload_all_parts_only_uploads_missing_parts() -> None:
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(b"0123456789" * 3)
        handle.flush()
        calls: list[str] = []

        def http_post(path: str, **kwargs):
            calls.append(path)
            return _part_response(int(path.rsplit("/", 1)[-1]))

        upload_all_parts(
            http_post=http_post,
            session=SimpleNamespace(id="s1", total_size=30, part_size=10, total_parts=3),
            file_path=Path(handle.name),
            part_size=10,
            total_parts=3,
            concurrency=1,
            missing_parts={2},
        )

    assert calls == ["/v1/uploads/s1/parts/2"]
