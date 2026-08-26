"""File object repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FileObject


async def get_file(
    session: AsyncSession,
    file_id: object,
    *,
    tenant_id: str | None = None,
    for_update: bool = False,
) -> FileObject | None:
    stmt = select(FileObject).where(FileObject.id == file_id)
    if tenant_id is not None:
        stmt = stmt.where(FileObject.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_file_by_object(
    session: AsyncSession,
    tenant_id: str,
    bucket: str,
    object_key: str,
) -> FileObject | None:
    result = await session.execute(
        select(FileObject).where(
            FileObject.tenant_id == tenant_id,
            FileObject.bucket == bucket,
            FileObject.object_key == object_key,
        )
    )
    return result.scalar_one_or_none()
