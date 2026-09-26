"""File listing API tests (GET /v1/files)."""

from __future__ import annotations

import io


def _upload(
    client,
    headers,
    object_key: str,
    body: bytes = b"data",
    content_type: str = "application/octet-stream",
    lifecycle: str | None = None,
) -> str:
    data = {"bucket": "app-default", "object_key": object_key}
    if lifecycle:
        data["lifecycle"] = lifecycle
    response = client.post(
        "/v1/files/upload",
        headers=headers,
        data=data,
        files={"file": ("f.bin", io.BytesIO(body), content_type)},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _keys(client, headers, **params) -> list[str]:
    response = client.get("/v1/files", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return [item["object_key"] for item in response.json()["items"]]


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

    # 已删除文件不可再读取/下载：应返回 404 而不是 500。
    assert client.get(f"/v1/files/{file_id}", headers=auth_headers).status_code == 404
    assert client.get(f"/v1/files/{file_id}/download", headers=auth_headers).status_code == 404


def test_list_files_validates_query_parameters(client, auth_headers):
    assert client.get("/v1/files", headers=auth_headers, params={"limit": 0}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"limit": 201}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"offset": -1}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"status": "bogus"}).status_code == 422
    assert client.get("/v1/files", headers=auth_headers, params={"sort_by": "size"}).status_code == 422


def test_list_files_sorts_by_every_column(client, auth_headers):
    """Every file-browser column is sortable (docs §16.2), in both directions."""
    prefix = "sort-all/"
    _upload(client, auth_headers, f"{prefix}b.txt", b"bb", "image/png")
    _upload(client, auth_headers, f"{prefix}a.txt", b"aaaa", "text/plain")
    _upload(client, auth_headers, f"{prefix}c.txt", b"c", "application/json")
    by_key = [f"{prefix}a.txt", f"{prefix}b.txt", f"{prefix}c.txt"]

    # object_key ascending by default; `name` is the historical alias of object_key
    assert _keys(client, auth_headers, prefix=prefix, sort_by="object_key") == by_key
    assert _keys(client, auth_headers, prefix=prefix, sort_by="name") == by_key
    assert (
        _keys(client, auth_headers, prefix=prefix, sort_by="object_key", sort_order="desc")
        == by_key[::-1]
    )

    # size_bytes: c(1) < b(2) < a(4)
    assert _keys(
        client, auth_headers, prefix=prefix, sort_by="size_bytes", sort_order="asc"
    ) == [f"{prefix}c.txt", f"{prefix}b.txt", f"{prefix}a.txt"]
    assert _keys(
        client, auth_headers, prefix=prefix, sort_by="size_bytes", sort_order="desc"
    ) == [f"{prefix}a.txt", f"{prefix}b.txt", f"{prefix}c.txt"]

    # content_type: application/json < image/png < text/plain
    assert _keys(client, auth_headers, prefix=prefix, sort_by="content_type") == [
        f"{prefix}c.txt",
        f"{prefix}b.txt",
        f"{prefix}a.txt",
    ]
    assert _keys(
        client, auth_headers, prefix=prefix, sort_by="content_type", sort_order="desc"
    ) == [f"{prefix}a.txt", f"{prefix}b.txt", f"{prefix}c.txt"]

    # created_at keeps its historical default (newest first) and is reversible
    newest_first = client.get(
        "/v1/files", headers=auth_headers, params={"prefix": prefix, "sort_by": "created_at"}
    ).json()["items"]
    stamps = [item["created_at"] for item in newest_first]
    assert stamps == sorted(stamps, reverse=True)
    assert {item["object_key"] for item in newest_first} == set(by_key)
    oldest_first = client.get(
        "/v1/files",
        headers=auth_headers,
        params={"prefix": prefix, "sort_by": "created_at", "sort_order": "asc"},
    ).json()["items"]
    ascending = [item["created_at"] for item in oldest_first]
    assert ascending == sorted(ascending)

    # Equal values still page deterministically: the tiebreaker is always object_key ascending,
    # so both directions agree here (all three rows share bucket and status).
    for field in ("bucket", "status"):
        assert _keys(client, auth_headers, prefix=prefix, sort_by=field) == by_key
        assert (
            _keys(client, auth_headers, prefix=prefix, sort_by=field, sort_order="desc") == by_key
        )


def test_list_files_keeps_permanent_files_last_when_sorting_by_expiry(client, auth_headers):
    prefix = "sort-expiry/"
    ttl = '{"mode":"ttl","ttl_seconds":3600}'
    _upload(client, auth_headers, f"{prefix}ttl-1.txt", lifecycle=ttl)
    _upload(client, auth_headers, f"{prefix}permanent.txt", lifecycle='{"mode":"permanent"}')
    _upload(client, auth_headers, f"{prefix}ttl-2.txt", lifecycle=ttl)
    permanent = f"{prefix}permanent.txt"
    expiring = {f"{prefix}ttl-1.txt", f"{prefix}ttl-2.txt"}

    ascending = _keys(
        client, auth_headers, prefix=prefix, sort_by="expires_at", sort_order="asc"
    )
    descending = _keys(
        client, auth_headers, prefix=prefix, sort_by="expires_at", sort_order="desc"
    )
    # A null expires_at means "permanent": those rows must not float to the top on DESC.
    assert ascending[-1] == permanent
    assert descending[-1] == permanent
    assert set(ascending[:2]) == expiring
    assert ascending[:2] != descending[:2]

    # Paging a sorted list must not repeat or skip rows within the filtered set.
    first = client.get(
        "/v1/files",
        headers=auth_headers,
        params={"prefix": prefix, "sort_by": "size_bytes", "limit": 2},
    ).json()["items"]
    second = client.get(
        "/v1/files",
        headers=auth_headers,
        params={"prefix": prefix, "sort_by": "size_bytes", "limit": 2, "offset": 2},
    ).json()["items"]
    assert len({item["id"] for item in first} | {item["id"] for item in second}) == 3

    assert (
        client.get(
            "/v1/files", headers=auth_headers, params={"sort_order": "sideways"}
        ).status_code
        == 422
    )
    assert (
        client.get("/v1/files", headers=auth_headers, params={"sort_by": "etag"}).status_code
        == 422
    )


def test_list_files_requires_auth(client):
    assert client.get("/v1/files").status_code == 401
