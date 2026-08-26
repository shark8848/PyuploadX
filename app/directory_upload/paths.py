"""Safe relative path normalization per docs_product-design.md section 13.2."""

from __future__ import annotations

import unicodedata

from app.core.errors import InvalidRelativePathError


_CONTROL_CHARS = {chr(code) for code in range(0, 32)} | {chr(127)}


def normalize_relative_path(
    raw_path: str,
    *,
    maximum_depth: int = 64,
    maximum_bytes: int = 1024,
) -> str:
    """Normalize a client-supplied relative path and reject unsafe values."""
    if "\x00" in raw_path:
        raise InvalidRelativePathError("path contains NUL character")
    if any(char in _CONTROL_CHARS for char in raw_path):
        raise InvalidRelativePathError("path contains control characters")

    posix_path = raw_path.replace("\\", "/")
    nfc_path = unicodedata.normalize("NFC", posix_path)
    if nfc_path.startswith("/"):
        raise InvalidRelativePathError("absolute paths are forbidden")
    if len(nfc_path) >= 2 and nfc_path[1] == ":":
        raise InvalidRelativePathError("windows drive paths are forbidden")

    parts: list[str] = []
    for part in nfc_path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise InvalidRelativePathError("parent directory traversal is forbidden")
        if part in {"~", "*", "?", '"', "<", ">", "|"}:
            raise InvalidRelativePathError(f"unsafe path segment: {part!r}")
        parts.append(part)

    normalized = "/".join(parts)
    if not normalized:
        raise InvalidRelativePathError("path must not be empty")
    if len(parts) > maximum_depth:
        raise InvalidRelativePathError(f"path exceeds maximum depth of {maximum_depth}")
    if len(normalized.encode("utf-8")) > maximum_bytes:
        raise InvalidRelativePathError(f"path exceeds maximum length of {maximum_bytes} bytes")
    return normalized


def join_prefix(prefix: str, relative_path: str) -> str:
    """Join a destination prefix and a normalized relative path."""
    normalized = normalize_relative_path(relative_path)
    clean_prefix = prefix.strip("/")
    if not clean_prefix:
        return normalized
    return f"{clean_prefix}/{normalized}"
