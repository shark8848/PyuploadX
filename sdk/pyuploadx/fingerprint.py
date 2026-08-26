"""Fast file fingerprint per docs_product-design.md section 12.3."""

from __future__ import annotations

import hashlib
from pathlib import Path


def fast_fingerprint(path: Path, sample_size: int = 64 * 1024) -> str:
    """Fast fingerprint from size, mtime and head/mid/tail samples."""
    stat = path.stat()
    size = stat.st_size
    digest = hashlib.sha256()
    digest.update(f"{size}:{stat.st_mtime_ns}".encode())
    if size > 0:
        with path.open("rb") as file:
            head = file.read(min(sample_size, size))
            digest.update(b"h" + head)
            if size > 3 * sample_size:
                file.seek(size // 2)
                digest.update(b"m" + file.read(sample_size))
                file.seek(-sample_size, 2)
                digest.update(b"t" + file.read(sample_size))
    return f"fp:{digest.hexdigest()[:40]}"


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
