"""Storage capability flags per docs_product-design.md section 15.2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StorageCapabilities:
    multipart: bool
    presigned_put: bool
    presigned_get: bool
    presigned_upload_part: bool
    list_parts: bool
    server_side_checksum: bool
    archive: bool
    transition: bool
    restore: bool
