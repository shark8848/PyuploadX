"""Bucket management and storage settings API tests."""

from __future__ import annotations

import io
import uuid


def _upload(client, headers, bucket: str, object_key: str, body: bytes = b"data") -> str:
    response = client.post(
        "/v1/files/upload",
        headers=headers,
        data={"bucket": bucket, "object_key": object_key},
        files={"file": ("f.bin", io.BytesIO(body), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_create_bucket_flow(client, auth_headers):
    name = "reports-" + uuid.uuid4().hex[:8]
    created = client.post("/v1/buckets", headers=auth_headers, json={"name": name})
    assert created.status_code == 201, created.text
    assert created.json()["name"] == name

    listed = client.get("/v1/buckets", headers=auth_headers)
    assert listed.status_code == 200
    assert name in listed.json()["buckets"]
    assert listed.json()["buckets"][:2] == ["app-default", "public-assets"]

    # 重复创建 → 409（存储层已存在）
    dup = client.post("/v1/buckets", headers=auth_headers, json={"name": name})
    assert dup.status_code == 409

    # 上传到新桶成功，client-config 反映新桶
    _upload(client, auth_headers, name, "docs/x.txt")
    cfg = client.get("/v1/client-config", headers=auth_headers)
    assert cfg.status_code == 200
    assert name in cfg.json()["uploads"]["allowed_buckets"]


def test_bucket_name_validation(client, auth_headers):
    for bad in ["UPPER", "ab", "a..b", "a-b-", "-abc", "has space"]:
        response = client.post("/v1/buckets", headers=auth_headers, json={"name": bad})
        assert response.status_code == 422, bad


def test_settings_defaults(client, auth_headers):
    got = client.get("/v1/settings", headers=auth_headers)
    assert got.status_code == 200
    storage = got.json()["storage"]
    assert storage["default_bucket"] == "app-default"
    assert storage["presign_default_expires_seconds"] == 900
    assert storage["maximum_expires_seconds"] == 86400


def test_update_settings(client, auth_headers):
    name = "settings-" + uuid.uuid4().hex[:8]
    assert client.post("/v1/buckets", headers=auth_headers, json={"name": name}).status_code == 201

    updated = client.put(
        "/v1/settings",
        headers=auth_headers,
        json={"storage": {"default_bucket": name, "presign_default_expires_seconds": 600}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["storage"]["default_bucket"] == name
    assert updated.json()["storage"]["presign_default_expires_seconds"] == 600

    cfg = client.get("/v1/client-config", headers=auth_headers).json()
    assert cfg["uploads"]["default_bucket"] == name
    assert cfg["presign"]["default_expires_seconds"] == 600

    # 非法值 → 422
    bad_bucket = client.put(
        "/v1/settings", headers=auth_headers, json={"storage": {"default_bucket": "nope"}}
    )
    assert bad_bucket.status_code == 422
    bad_presign = client.put(
        "/v1/settings",
        headers=auth_headers,
        json={"storage": {"default_bucket": name, "presign_default_expires_seconds": 10}},
    )
    assert bad_presign.status_code == 422

    # 还原默认值，避免影响同会话的其他测试
    restore = client.put(
        "/v1/settings",
        headers=auth_headers,
        json={"storage": {"default_bucket": "app-default", "presign_default_expires_seconds": 900}},
    )
    assert restore.status_code == 200
