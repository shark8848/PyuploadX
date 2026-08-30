"""SDK against an in-process ASGI app (docs 17)."""

from __future__ import annotations

import httpx
from pyuploadx.exceptions import ValidationError


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
        with_dir = client.upload_file(str(source), bucket="app-default", directory="reports/2026")
        assert with_dir.object_key == "reports/2026/report.pdf"
        try:
            client.upload_file(str(source), bucket="app-default", directory="../evil")
            raise AssertionError("expected ValidationError")
        except ValidationError:
            pass
        fetched = client.get_file(info.id)
        assert fetched.id == info.id
        dest = tmp_path / "downloaded.bin"
        saved = client.download(info.id, str(dest))          # 代理流式下载
        assert saved == dest
        assert dest.read_bytes() == source.read_bytes()


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
        info2 = client.upload_large_file(
            str(source),
            bucket="app-default",
            directory="models/backup",
            part_size=5,
            concurrency=2,
        )
        assert info2.object_key == "models/backup/model.bin"
        session = client.create_upload(
            bucket="app-default",
            object_key="models/session-probe.bin",
            total_size=10,
            part_size=5,
        )
        fetched_session = client.get_upload(session.id)
        assert fetched_session.id == session.id
        assert fetched_session.status == "initiated"


def test_sdk_download_from_url(app, auth_headers, tmp_path):
    source = tmp_path / "demo.bin"
    source.write_bytes(b"url-download-body")
    with _make_client(app, auth_headers) as client:
        info = client.upload_file(str(source), bucket="app-default")
        import httpx as _httpx

        with _httpx.Client(transport=SyncASGITransport(app)) as raw:
            link = raw.post(
                f"http://testserver/v1/files/{info.id}/permanent-link",
                headers=auth_headers,
            ).json()["url"]

        dest = tmp_path / "from-url.bin"
        progress: list[tuple[int, int]] = []
        saved = client.download_from_url(
            link, str(dest), progress=lambda w, t: progress.append((w, t))
        )
        assert saved == dest
        assert dest.read_bytes() == source.read_bytes()
        assert progress[-1][0] == len(b"url-download-body")

        dest2 = tmp_path / "via-download.bin"
        saved2 = client.download(info.id, str(dest2), url=link)   # download(url=...) 等价
        assert saved2 == dest2
        assert dest2.read_bytes() == source.read_bytes()


def test_sdk_download_parallel(app, auth_headers, tmp_path):
    body = bytes(range(256)) * 64  # 16 KiB, exercises multiple Range requests
    source = tmp_path / "big.bin"
    source.write_bytes(body)
    with _make_client(app, auth_headers) as client:
        info = client.upload_file(str(source), bucket="app-default")

        dest = tmp_path / "parallel.bin"
        progress: list[tuple[int, int]] = []
        saved = client.download(
            info.id,
            str(dest),
            concurrency=4,
            progress=lambda w, t: progress.append((w, t)),
        )
        assert saved == dest
        assert dest.read_bytes() == body
        assert progress[-1] == (len(body), len(body))

        import httpx as _httpx

        with _httpx.Client(transport=SyncASGITransport(app)) as raw:
            link = raw.post(
                f"http://testserver/v1/files/{info.id}/permanent-link",
                headers=auth_headers,
            ).json()["url"]
        dest2 = tmp_path / "parallel-url.bin"
        saved2 = client.download_from_url(link, str(dest2), concurrency=4)
        assert saved2 == dest2
        assert dest2.read_bytes() == body


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
