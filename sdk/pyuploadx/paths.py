"""Client-side relative path normalization (mirrors server contract)."""

from __future__ import annotations

import unicodedata

from pyuploadx.exceptions import ValidationError


def normalize_relative_path(raw_path: str, maximum_depth: int = 64, maximum_bytes: int = 1024) -> str:
    posix_path = raw_path.replace("\\", "/")
    nfc_path = unicodedata.normalize("NFC", posix_path)
    if nfc_path.startswith("/"):
        raise ValidationError("absolute paths are forbidden")
    if len(nfc_path) >= 2 and nfc_path[1] == ":":
        raise ValidationError("windows drive paths are forbidden")
    parts: list[str] = []
    for part in nfc_path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValidationError("parent directory traversal is forbidden")
        parts.append(part)
    normalized = "/".join(parts)
    if not normalized:
        raise ValidationError("path must not be empty")
    if len(parts) > maximum_depth:
        raise ValidationError(f"path exceeds maximum depth of {maximum_depth}")
    if len(normalized.encode("utf-8")) > maximum_bytes:
        raise ValidationError(f"path exceeds maximum length of {maximum_bytes} bytes")
    return normalized
