"""SDK against an in-process ASGI app (docs 17)."""

from __future__ import annotations

import httpx


class SyncASGITransport(httpx.BaseTransport):
    """Bridge httpx 0.28 async-only ASGITransport to the sync client for tests."""

    def __init__(self, app):
        self._inner = httpx.ASGITransport(app=app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        import asyncio

        response = asyncio.run(self._inner.handle_async_request(request))
        content = asyncio.run(response.aread())
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=content,
            request=request,
        )

    def close(self) -> None:
        import asyncio

        try:
            asyncio.run(self._inner.aclose())
        except RuntimeError:
            pass


def _make_client(app, auth_headers):
    from pyuploadx import UploadClient

    return UploadClient(
        base_url="http://testserver",
        api_key=auth_headers["X-API-Key"],
        state_dir="/tmp/pyuploadx-sdk-state",
        transport=SyncASGITransport(app),
    )


def test_sdk_upload_file(app, auth_headers, tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4 fake content")
    with _make_client(app, auth_headers) as client:
        info = client.upload_file(str(source), bucket="app-default")
        assert info.size_bytes == len(b"%PDF-1.4 fake content")
        assert info.status == "active"
        assert info.download_url is None          # Local backend: no presigned_get
        assert info.expires_in is None
        assert client.get_download_url(info.id) is None
        fetched = client.get_file(info.id)
        assert fetched.id == info.id


def test_sdk_large_file_multipart(app, auth_headers, tmp_path):
    source = tmp_path / "model.bin"
    source.write_bytes(b"0123456789")
    with _make_client(app, auth_headers) as client:
        info = client.upload_large_file(
            str(source),
            bucket="app-default",
            object_key="models/model.bin",
            part_size=5,
            concurrency=2,
        )
        assert info.size_bytes == 10
        assert info.object_key == "models/model.bin"
        assert info.download_url is None
        session = client.create_upload(
            bucket="app-default",
            object_key="models/session-probe.bin",
            total_size=10,
            part_size=5,
        )
        fetched_session = client.get_upload(session.id)
        assert fetched_session.id == session.id
        assert fetched_session.status == "initiated"


def test_sdk_directory_upload(app, auth_headers, tmp_path):
    root = tmp_path / "album"
    (root / "images").mkdir(parents=True)
    (root / "images" / "cover.jpg").write_bytes(b"jpeg-data")
    (root / "README.md").write_text("# album")
    (root / ".uploadignore").write_text("*.tmp\n")
    (root / "scratch.tmp").write_text("ignored")
    with _make_client(app, auth_headers) as client:
        job = client.upload_directory(
            str(root),
            bucket="app-default",
            destination_prefix="artists/1",
            file_concurrency=2,
            part_concurrency=2,
        )
        assert job.status == "completed"
        assert job.total_files == 2
        fetched_job = client.get_directory_job(job.id)
        assert fetched_job.id == job.id
        assert fetched_job.status == "completed"
        assert fetched_job.uploaded_files == 2
