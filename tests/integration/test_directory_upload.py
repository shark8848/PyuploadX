"""Directory upload API flow (docs 13, 16.6)."""

from __future__ import annotations


def test_directory_upload_flow(client, auth_headers):
    created = client.post(
        "/v1/directory-uploads",
        headers=auth_headers,
        json={
            "root_directory_name": "album",
            "bucket": "app-default",
            "destination_prefix": "artists/10001",
            "conflict_policy": "reject",
        },
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    assert created.json()["status"] == "created"

    entries = [
        {"entry_type": "directory", "relative_path": "images", "size_bytes": 0},
        {"entry_type": "file", "relative_path": "images/cover.jpg", "size_bytes": 1024},
        {"entry_type": "file", "relative_path": "README.md", "size_bytes": 2048},
    ]
    added = client.post(
        f"/v1/directory-uploads/{job_id}/entries", headers=auth_headers, json={"entries": entries}
    )
    assert added.status_code == 200
    assert added.json()["added"] == 3

    from app.directory_upload.manifest import manifest_hash_from_entries

    manifest_hash = manifest_hash_from_entries(
        [
            {"relative_path": "images/cover.jpg", "size_bytes": 1024, "fingerprint": None},
            {"relative_path": "README.md", "size_bytes": 2048, "fingerprint": None},
        ]
    )
    finalized = client.post(
        f"/v1/directory-uploads/{job_id}/manifest/complete",
        headers=auth_headers,
        json={"manifest_hash": manifest_hash, "counts": {"files": 2, "directories": 1}},
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "ready"

    listed = client.get(f"/v1/directory-uploads/{job_id}/entries", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()["entries"]) == 3
    keys = {row["object_key"] for row in listed.json()["entries"]}
    assert "artists/10001/images/cover.jpg" in keys

    retried = client.post(f"/v1/directory-uploads/{job_id}/retry", headers=auth_headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "uploading"

    completed = client.post(f"/v1/directory-uploads/{job_id}/complete", headers=auth_headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"


def test_directory_upload_rejects_traversal(client, auth_headers):
    created = client.post(
        "/v1/directory-uploads",
        headers=auth_headers,
        json={
            "root_directory_name": "evil",
            "bucket": "app-default",
            "destination_prefix": "p",
        },
    )
    job_id = created.json()["id"]
    response = client.post(
        f"/v1/directory-uploads/{job_id}/entries",
        headers=auth_headers,
        json={"entries": [{"entry_type": "file", "relative_path": "../secret.txt", "size_bytes": 1}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_RELATIVE_PATH"
