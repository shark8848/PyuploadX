"""File object repository."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FileObject, FileStatus


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


async def list_files(
    session: AsyncSession,
    *,
    tenant_id: str,
    bucket: str | None = None,
    prefix: str | None = None,
    status: FileStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    order_by: str = "name",
) -> tuple[list[FileObject], int]:
    """Page over file objects for a tenant with optional filters."""
    conditions = [FileObject.tenant_id == tenant_id]
    if bucket is not None:
        conditions.append(FileObject.bucket == bucket)
    if prefix:
        conditions.append(FileObject.object_key.startswith(prefix))
    if status is not None:
        conditions.append(FileObject.status == status)

    total = (
        await session.execute(select(func.count()).select_from(FileObject).where(*conditions))
    ).scalar_one()

    stmt = select(FileObject).where(*conditions)
    if order_by == "created_at":
        stmt = stmt.order_by(FileObject.created_at.desc(), FileObject.object_key.asc())
    else:
        stmt = stmt.order_by(FileObject.object_key.asc(), FileObject.created_at.desc())
    result = await session.execute(stmt.offset(offset).limit(limit))
    return list(result.scalars().all()), total
