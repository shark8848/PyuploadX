"""Bucket management service."""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Identity
from app.core.errors import ApiError
from app.db import repositories
from app.storage.base import StorageAdapter

_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


class BucketService:
    def __init__(self, settings, storage: StorageAdapter) -> None:
        self.settings = settings
        self.storage = storage

    def validate_name(self, name: str) -> str:
        name = (name or "").strip()
        if not _BUCKET_NAME_RE.fullmatch(name) or ".." in name:
            raise ApiError(
                "INVALID_BUCKET_NAME",
                "Bucket name must be 3-63 chars of lowercase letters, digits, dots and hyphens.",
                status_code=422,
            )
        return name

    async def create_bucket(
        self,
        session: AsyncSession,
        identity: Identity,
        name: str,
    ) -> dict[str, str]:
        name = self.validate_name(name)
        if await self.storage.bucket_exists(name):
            raise ApiError(
                "BUCKET_ALREADY_EXISTS",
                f"Bucket {name!r} already exists.",
                status_code=409,
            )
        if await repositories.bucket_repository.get_by_name(session, identity.tenant_id, name):
            raise ApiError(
                "BUCKET_ALREADY_EXISTS",
                f"Bucket {name!r} already exists.",
                status_code=409,
            )
        await self.storage.create_bucket(name)
        bucket = await repositories.bucket_repository.create(
            session,
            tenant_id=identity.tenant_id,
            name=name,
            created_by=identity.principal_id,
        )
        return {
            "name": bucket.name,
            "created_at": bucket.created_at.isoformat(),
        }

    async def list_buckets_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str,
    ) -> list[str]:
        names = set(self.settings.storage.allowed_buckets)
        for row in await repositories.bucket_repository.list_for_tenant(session, tenant_id):
            names.add(row.name)
        return sorted(names)

    async def list_managed_buckets_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str,
    ) -> list[str]:
        rows = await repositories.bucket_repository.list_for_tenant(session, tenant_id)
        return [row.name for row in rows]

    async def delete_bucket(
        self,
        session: AsyncSession,
        identity: Identity,
        name: str,
    ) -> dict[str, str]:
        name = self.validate_name(name)
        if name in self.settings.storage.allowed_buckets:
            raise ApiError(
                "BUCKET_NOT_DELETABLE",
                f"Bucket {name!r} is configured and cannot be deleted.",
                status_code=403,
            )
        record = await repositories.bucket_repository.get_by_name(
            session, identity.tenant_id, name
        )
        if not record:
            raise ApiError(
                "BUCKET_NOT_FOUND",
                f"Bucket {name!r} does not exist.",
                status_code=404,
            )
        if not await self.storage.bucket_exists(name):
            raise ApiError(
                "BUCKET_NOT_FOUND",
                f"Bucket {name!r} does not exist.",
                status_code=404,
            )
        await self.storage.delete_bucket(name)
        await repositories.bucket_repository.delete(session, record)
        return {"name": name}

    async def is_bucket_allowed(
        self,
        session: AsyncSession,
        tenant_id: str,
        bucket: str,
    ) -> bool:
        if bucket in self.settings.storage.allowed_buckets:
            return True
        return (
            await repositories.bucket_repository.get_by_name(session, tenant_id, bucket)
            is not None
        )
