"""Directory manifest hashing and (ND)JSON handling per docs_product-design.md 13.4."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.errors import ManifestHashMismatchError


def manifest_hash_from_entries(entries: list[dict[str, Any]]) -> str:
    """Hash based on normalized, sorted (relative_path, size_bytes, fingerprint)."""
    lines: list[str] = []
    for entry in sorted(entries, key=lambda item: item.get("relative_path", "")):
        lines.append(
            json.dumps(
                {
                    "relative_path": entry.get("relative_path", ""),
                    "size_bytes": entry.get("size_bytes", 0),
                    "fingerprint": entry.get("fingerprint"),
                },
                sort_keys=True,
                ensure_ascii=False,
            )
        )
    digest = hashlib.sha256()
    digest.update("\n".join(lines).encode("utf-8"))
    return digest.hexdigest()


def serialize_manifest_ndjson(entries: list[dict[str, Any]]) -> str:
    lines = []
    for entry in entries:
        payload = {
            "entry_type": entry.get("entry_type", "file"),
            "relative_path": entry.get("relative_path"),
            "size_bytes": entry.get("size_bytes", 0),
        }
        if entry.get("fingerprint") is not None:
            payload["fingerprint"] = entry["fingerprint"]
        if entry.get("last_modified_ns") is not None:
            payload["last_modified_ns"] = entry["last_modified_ns"]
        lines.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def parse_manifest_ndjson(payload: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in payload.splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(json.loads(line))
    return entries


def verify_manifest_hash(
    entries: list[dict[str, Any]],
    expected_hash: str | None,
) -> None:
    if expected_hash is None:
        return
    actual = manifest_hash_from_entries(entries)
    if actual != expected_hash:
        raise ManifestHashMismatchError(expected_hash, actual)
