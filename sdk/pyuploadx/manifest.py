"""Manifest hashing and NDJSON serialization (docs 13.4)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def manifest_hash_from_entries(entries: list[dict[str, Any]]) -> str:
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
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def serialize_ndjson(entries: list[dict[str, Any]]) -> str:
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
