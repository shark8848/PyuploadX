"""End-to-end API tests: proxy upload, download, delete (docs 11.1, 16.2)."""

from __future__ import annotations

import io


def test_proxy_upload_download_delete(client, auth_headers):
    response = client.post(
        "/v1/files/upload",
        headers=auth_headers,
        data={"bucket": "app-default", "object_key": "docs/readme.md"},
        files={"file": ("readme.md", io.BytesIO(b"# hello"), "text/markdown")},
    )
    assert response.status_code == 200, response.text
    file_info = response.json()
    assert file_info["object_key"] == "docs/readme.md"
    assert file_info["size_bytes"] == 7
    assert file_info["status"] == "active"
    file_id = file_info["id"]

    fetched = client.get(f"/v1/files/{file_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == file_id

    downloaded = client.get(f"/v1/files/{file_id}/download", headers=auth_headers)
    assert downloaded.status_code == 200
    assert downloaded.content == b"# hello"
    assert "ETag" in downloaded.headers

    deleted = client.delete(f"/v1/files/{file_id}", headers=auth_headers)
    assert deleted.status_code == 200


def test_proxy_upload_conflict_policy(client, auth_headers):
    payload = {
        "bucket": "app-default",
        "object_key": "docs/conflict.txt",
    }
    for _ in range(2):
        response = client.post(
            "/v1/files/upload",
            headers=auth_headers,
            data=payload,
            files={"file": ("conflict.txt", io.BytesIO(b"x"), "text/plain")},
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OBJECT_ALREADY_EXISTS"


def test_upload_requires_auth(client):
    response = client.post(
        "/v1/files/upload",
        data={"bucket": "app-default", "object_key": "x.txt"},
        files={"file": ("x.txt", io.BytesIO(b"x"), "text/plain")},
    )
    assert response.status_code == 401


def test_error_format_has_request_id(client, auth_headers):
    response = client.get("/v1/files/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "FILE_NOT_FOUND"
    assert body["retryable"] is False
    assert "X-Request-ID" in response.headers


def test_lifecycle_flow(client, auth_headers):
    response = client.post(
        "/v1/files/upload",
        headers=auth_headers,
        data={
            "bucket": "app-default",
            "object_key": "lifecycle/a.bin",
            "lifecycle": '{"mode":"ttl","ttl_seconds":3600}',
        },
        files={"file": ("a.bin", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert response.status_code == 200
    file_id = response.json()["id"]
    lifecycle = client.get(f"/v1/files/{file_id}/lifecycle", headers=auth_headers)
    assert lifecycle.status_code == 200
    assert lifecycle.json()["mode"] == "ttl"
    assert lifecycle.json()["expires_at"] is not None

    extended = client.post(
        f"/v1/files/{file_id}/lifecycle/extend",
        headers=auth_headers,
        json={"extend_seconds": 3600},
    )
    assert extended.status_code == 200

    hold = client.post(f"/v1/files/{file_id}/legal-hold", headers=auth_headers)
    assert hold.status_code == 200
    blocked = client.delete(f"/v1/files/{file_id}", headers=auth_headers)
    assert blocked.status_code == 409
    released = client.delete(f"/v1/files/{file_id}/legal-hold", headers=auth_headers)
    assert released.status_code == 200


def test_range_download(client, auth_headers):
    body = b"0123456789"
    response = client.post(
        "/v1/files/upload",
        headers=auth_headers,
        data={"bucket": "app-default", "object_key": "range/data.bin"},
        files={"file": ("data.bin", io.BytesIO(body), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    file_id = response.json()["id"]

    full = client.get(f"/v1/files/{file_id}/download", headers=auth_headers)
    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    assert full.content == body

    part = client.get(
        f"/v1/files/{file_id}/download",
        headers={**auth_headers, "Range": "bytes=2-5"},
    )
    assert part.status_code == 206
    assert part.content == b"2345"
    assert part.headers["content-range"] == "bytes 2-5/10"
    assert part.headers["accept-ranges"] == "bytes"

    tail = client.get(
        f"/v1/files/{file_id}/download",
        headers={**auth_headers, "Range": "bytes=7-"},
    )
    assert tail.status_code == 206
    assert tail.content == b"789"

    suffix = client.get(
        f"/v1/files/{file_id}/download",
        headers={**auth_headers, "Range": "bytes=-3"},
    )
    assert suffix.status_code == 206
    assert suffix.content == b"789"

    unsatisfiable = client.get(
        f"/v1/files/{file_id}/download",
        headers={**auth_headers, "Range": "bytes=10-"},
    )
    assert unsatisfiable.status_code == 416
    assert unsatisfiable.json()["error"]["code"] == "RANGE_NOT_SATISFIABLE"

    link_resp = client.post(f"/v1/files/{file_id}/permanent-link", headers=auth_headers)
    assert link_resp.status_code == 200, link_resp.text
    link = link_resp.json()["url"]
    linked = client.get(link, headers={"Range": "bytes=0-4"})
    assert linked.status_code == 206
    assert linked.content == b"01234"
    assert linked.headers["content-range"] == "bytes 0-4/10"
