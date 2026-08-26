"""Multipart upload orchestration: proxy part PUTs with concurrency and retry."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any

from pyuploadx.exceptions import MultipartError
from pyuploadx.models import UploadedPart
from pyuploadx.retry import retry
from pyuploadx.scheduler import Scheduler


def _part_sha256(path: Path, offset: int, size: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        file.seek(offset)
        remaining = size
        while remaining > 0:
            chunk = file.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def upload_all_parts(
    *,
    http_post,
    session: Any,
    file_path: Path,
    part_size: int,
    total_parts: int,
    concurrency: int,
    max_total_concurrent: int = 32,
    progress: Any = None,
) -> list[UploadedPart]:
    """Upload every part of a file through the proxy endpoint."""
    uploaded: list[UploadedPart] = []
    lock = threading.Lock()
    scheduler = Scheduler(
        max_workers=max(1, concurrency),
        max_concurrent_requests=max_total_concurrent,
    )

    def upload_part(part_number: int) -> None:
        offset = (part_number - 1) * part_size
        size = min(part_size, session.total_size - offset)
        checksum = _part_sha256(file_path, offset, size)
        with file_path.open("rb") as file:
            file.seek(offset)
            body = file.read(size)
        response = retry(
            lambda: http_post(
                f"/v1/uploads/{session.id}/parts/{part_number}",
                content=body,
                headers={"X-Part-SHA256": checksum},
            )
        )
        payload = response.json()
        if response.status_code >= 400:
            raise MultipartError(payload.get("error", {}).get("message", "part upload failed"))
        with lock:
            uploaded.append(
                UploadedPart(
                    part_number=payload["part_number"],
                    etag=payload["etag"],
                    size_bytes=payload["size_bytes"],
                    checksum_sha256=payload.get("checksum_sha256"),
                )
            )
            if progress is not None:
                progress(part_number, total_parts)

    try:
        for part_number in range(1, total_parts + 1):
            scheduler.submit(upload_part, part_number)
        scheduler.wait_all()
    finally:
        scheduler.shutdown()
    return sorted(uploaded, key=lambda part: part.part_number)
