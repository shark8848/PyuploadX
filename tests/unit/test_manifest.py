"""Manifest hash tests (docs 13.4)."""

from __future__ import annotations

import pytest

from app.core.errors import ManifestHashMismatchError
from app.directory_upload.manifest import (
    manifest_hash_from_entries,
    parse_manifest_ndjson,
    serialize_manifest_ndjson,
    verify_manifest_hash,
)


def test_manifest_hash_order_independent():
    entries = [
        {"relative_path": "b.txt", "size_bytes": 2, "fingerprint": "fp:2"},
        {"relative_path": "a.txt", "size_bytes": 1, "fingerprint": "fp:1"},
    ]
    assert manifest_hash_from_entries(entries) == manifest_hash_from_entries(list(reversed(entries)))


def test_manifest_hash_sensitive_to_content():
    first = manifest_hash_from_entries([{"relative_path": "a.txt", "size_bytes": 1}])
    second = manifest_hash_from_entries([{"relative_path": "a.txt", "size_bytes": 2}])
    assert first != second


def test_ndjson_roundtrip():
    entries = [
        {"entry_type": "file", "relative_path": "README.md", "size_bytes": 2048},
        {"entry_type": "file", "relative_path": "images/cover.jpg", "size_bytes": 5242880},
    ]
    payload = serialize_manifest_ndjson(entries)
    parsed = parse_manifest_ndjson(payload)
    assert parsed == entries


def test_verify_manifest_hash_mismatch():
    with pytest.raises(ManifestHashMismatchError):
        verify_manifest_hash([{"relative_path": "a", "size_bytes": 1}], "deadbeef")
