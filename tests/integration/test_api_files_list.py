"""File listing API tests (GET /v1/files)."""

from __future__ import annotations

import io


def _upload(client, headers, object_key: str, body: bytes = b"data") -> str:
    response = client.post(
        "/v1/files/upload",
        headers=headers,
        data={"bucket": "app-default", "object_key": object_key},
        files={"file": ("f.bin", io.BytesIO(body), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_list_files_pagination_and_filters(client, auth_headers):
    docs_ids = [_upload(client, auth_headers, f"p1/docs/{i}.txt") for i in range(5)]
    asset_id = _upload(client, auth_headers, "p1/assets/logo.svg", b"<svg/>")

    page = client.get("/v1/files", headers=auth_headers, params={"prefix": "p1/"})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 6
    assert [item["id"] for item in body["items"]] == [asset_id, *docs_ids]
    assert all(item["status"] == "active" for item in body["items"])

    filtered = client.get(
        "/v1/files", headers=auth_headers, params={"bucket": "app-default", "prefix": "p1/docs/"}
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 5
    assert [item["id"] for item in filtered.json()["items"]] == docs_ids

    paged = client.get(
        "/v1/files", headers=auth_headers, params={"prefix": "p1/", "limit": 2, "offset": 1}
    )
    assert paged.status_code == 200
    assert paged.json()["total"] == 6
    assert len(paged.json()["items"]) == 2

    newest = client.get(
        "/v1/files", headers=auth_headers, params={"prefix": "p1/", "sort_by": "created_at"}
    )
    assert newest.status_code == 200
    assert sorted(item["id"] for item in newest.json()["items"]) == sorted([asset_id, *docs_ids])


def test_list_files_defaults_to_active_only(client, auth_headers):
    file_id = _upload(client, auth_headers, "p2/docs/keep.txt")
    _upload(client, auth_headers, "p2/docs/drop.txt")
    deleted = client.delete(f"/v1/files/{file_id}", headers=auth_headers)
    assert deleted.status_code == 200

    active = client.get("/v1/files", headers=auth_headers, params={"prefix": "p2/docs/"})
    assert active.status_code == 200
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["object_key"] == "p2/docs/drop.txt"

    including_deleted = client.get(
        "/v1/files", headers=auth_headers, params={"prefix": "p2/docs/", "status": "deleted"}
    )
    assert including_deleted.status_code == 200
    assert including_deleted.json()["total"] == 1
    assert including_deleted.json()["items"][0]["object_key"] == "p2/docs/keep.txt"


def test_list_files_validates_query_parameters(client, auth_headers):
    assert client.get("/v1/files", headers=auth_headers, params={"limit": 0}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"limit": 201}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"offset": -1}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"status": "bogus"}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"sort_by": "size"}).status_code == 422


def test_list_files_requires_auth(client):
    assert client.get("/v1/files").status_code == 401
