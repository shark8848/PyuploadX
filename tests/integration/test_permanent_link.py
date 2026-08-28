"""Permanent download links (docs 16.2): create + unauthenticated download."""

from __future__ import annotations

import io


def _upload(client, auth_headers, object_key=None):
    import uuid

    object_key = object_key or f"links/{uuid.uuid4().hex}.txt"
    response = client.post(
        "/v1/files/upload",
        headers=auth_headers,
        data={"bucket": "app-default", "object_key": object_key},
        files={"file": ("demo.txt", io.BytesIO(b"permanent-link-body"), "text/plain")},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_permanent_link_create_and_download(client, auth_headers):
    file_id = _upload(client, auth_headers)

    created = client.post(f"/v1/files/{file_id}/permanent-link", headers=auth_headers)
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["permanent"] is True
    assert payload["url"].startswith("http://testserver/v1/files/")
    assert "/download-link?token=" in payload["url"]

    # 无需鉴权即可下载
    downloaded = client.get(payload["url"])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == b"permanent-link-body"


def test_permanent_link_wrong_token_rejected(client, auth_headers):
    file_id = _upload(client, auth_headers)
    response = client.get(f"/v1/files/{file_id}/download-link?token=wrong-token")
    assert response.status_code == 403


def test_permanent_link_after_delete_not_found(client, auth_headers):
    file_id = _upload(client, auth_headers)
    created = client.post(f"/v1/files/{file_id}/permanent-link", headers=auth_headers).json()
    assert client.delete(f"/v1/files/{file_id}", headers=auth_headers).status_code == 200
    response = client.get(created["url"])
    assert response.status_code == 404
