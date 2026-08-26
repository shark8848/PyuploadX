"""Memory-safe streaming helpers: spool request bodies to disk."""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from dataclasses import dataclass
from typing import BinaryIO

from fastapi import Request


@dataclass
class SpooledFile:
    file: BinaryIO
    size_bytes: int
    sha256: str

    def close(self) -> None:
        self.file.close()


async def spool_request(request: Request, max_memory: int = 1024 * 1024) -> SpooledFile:
    """Stream the request body into a spooled temporary file, computing size and SHA-256."""
    spooled = tempfile.SpooledTemporaryFile(max_size=max_memory, mode="w+b")
    digest = hashlib.sha256()
    total = 0
    try:
        async for chunk in request.stream():
            if chunk:
                digest.update(chunk)
                total += len(chunk)
                await asyncio.to_thread(spooled.write, chunk)
        spooled.seek(0)
    except Exception:
        spooled.close()
        raise
    return SpooledFile(file=spooled, size_bytes=total, sha256=digest.hexdigest())
