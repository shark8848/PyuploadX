"""Bucket repository (storage_buckets table)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StorageBucket


async def get_by_name(
    session: AsyncSession,
    tenant_id: str,
    name: str,
) -> StorageBucket | None:
    result = await session.execute(
        select(StorageBucket).where(
            StorageBucket.tenant_id == tenant_id,
            StorageBucket.name == name,
        )
    )
    return result.scalar_one_or_none()


async def list_for_tenant(session: AsyncSession, tenant_id: str) -> list[StorageBucket]:
    result = await session.execute(
        select(StorageBucket)
        .where(StorageBucket.tenant_id == tenant_id)
        .order_by(StorageBucket.name)
    )
    return list(result.scalars().all())


async def create(
    session: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    created_by: str,
) -> StorageBucket:
    bucket = StorageBucket(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        created_by=created_by,
    )
    session.add(bucket)
    await session.flush()
    return bucket
