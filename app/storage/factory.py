"""Build a storage adapter from settings."""

from __future__ import annotations

from app.config.models import Settings
from app.storage.base import StorageAdapter
from app.storage.local import LocalStorageAdapter
from app.storage.s3 import S3StorageAdapter


def build_storage(settings: Settings) -> StorageAdapter:
    if settings.storage.backend == "local":
        return LocalStorageAdapter(config=settings.storage.local)
    return S3StorageAdapter(config=settings.storage.s3)
