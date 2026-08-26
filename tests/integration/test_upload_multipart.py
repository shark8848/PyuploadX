"""Multipart upload flow via the API (docs 11.2/11.3, 16.4)."""

from __future__ import annotations

import io


def test_multipart_proxy_upload_flow(client, auth_headers):
    body = {
        "bucket": "app-default",
        "object_key": "models/api-model.bin",
        "original_filename": "model.bin",
        "total_size": 10,
        "part_size": 5,
        "upload_mode": "proxy",
    }
    created = client.post("/v1/uploads", headers=auth_headers, json=body)
    assert created.status_code == 200, created.text
    session = created.json()
    upload_id = session["id"]
    assert session["total_parts"] == 2

    first = client.put(
        f"/v1/uploads/{upload_id}/parts/1",
        headers={**auth_headers, "X-Part-SHA256": "0" * 64},
        content=b"hello",
    )
    assert first.status_code == 200, first.text

    second = client.put(
        f"/v1/uploads/{upload_id}/parts/2",
        headers={**auth_headers, "X-Part-SHA256": "0" * 64},
        content=b"world",
    )
    assert second.status_code == 200

    parts = client.get(f"/v1/uploads/{upload_id}/parts", headers=auth_headers)
    assert len(parts.json()["parts"]) == 2

    completed = client.post(f"/v1/uploads/{upload_id}/complete", headers=auth_headers)
    assert completed.status_code == 200, completed.text
    file_info = completed.json()
    assert file_info["size_bytes"] == 10
    assert file_info["bucket"] == "app-default"

    # Complete is idempotent: same file_id returned.
    again = client.post(f"/v1/uploads/{upload_id}/complete", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["id"] == file_info["id"]

    downloaded = client.get(f"/v1/files/{file_info['id']}/download", headers=auth_headers)
    assert downloaded.content == b"helloworld"


def test_complete_with_missing_parts(client, auth_headers):
    created = client.post(
        "/v1/uploads",
        headers=auth_headers,
        json={
            "bucket": "app-default",
        "object_key": "models/api-missing.bin",
            "total_size": 10,
            "part_size": 5,
            "upload_mode": "proxy",
        },
    )
    upload_id = created.json()["id"]
    client.put(
        f"/v1/uploads/{upload_id}/parts/1",
        headers=auth_headers,
        content=b"hello",
    )
    completed = client.post(f"/v1/uploads/{upload_id}/complete", headers=auth_headers)
    assert completed.status_code == 409
    assert completed.json()["error"]["code"] == "MISSING_PARTS"


def test_abort_flow(client, auth_headers):
    created = client.post(
        "/v1/uploads",
        headers=auth_headers,
        json={
            "bucket": "app-default",
        "object_key": "models/api-abort.bin",
            "total_size": 10,
            "part_size": 5,
            "upload_mode": "proxy",
        },
    )
    upload_id = created.json()["id"]
    aborted = client.post(f"/v1/uploads/{upload_id}/abort", headers=auth_headers)
    assert aborted.status_code == 200
    assert aborted.json()["status"] == "aborted"
    # abort is idempotent
    again = client.post(f"/v1/uploads/{upload_id}/abort", headers=auth_headers)
    assert again.status_code == 200


def test_resume_returns_missing_parts(client, auth_headers):
    created = client.post(
        "/v1/uploads",
        headers=auth_headers,
        json={
            "bucket": "app-default",
        "object_key": "models/api-resume.bin",
            "total_size": 10,
            "part_size": 5,
            "upload_mode": "proxy",
        },
    )
    upload_id = created.json()["id"]
    client.put(f"/v1/uploads/{upload_id}/parts/1", headers=auth_headers, content=b"hello")
    resumed = client.post(
        "/v1/uploads/resume", headers=auth_headers, json={"upload_id": upload_id}
    )
    assert resumed.status_code == 200
    assert resumed.json()["missing_parts"] == [2]
