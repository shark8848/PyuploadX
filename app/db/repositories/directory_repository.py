"""Directory upload job and entry repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DirectoryUploadEntry,
    DirectoryUploadJob,
    DirectoryJobStatus,
)


async def get_job(
    session: AsyncSession,
    job_id: object,
    *,
    tenant_id: str | None = None,
    for_update: bool = False,
) -> DirectoryUploadJob | None:
    stmt = select(DirectoryUploadJob).where(DirectoryUploadJob.id == job_id)
    if tenant_id is not None:
        stmt = stmt.where(DirectoryUploadJob.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_job_status(
    session: AsyncSession,
    job_id: object,
    status: DirectoryJobStatus,
) -> None:
    values: dict = {"status": status, "updated_at": datetime.utcnow()}
    if status in (DirectoryJobStatus.completed, DirectoryJobStatus.completed_with_errors):
        values["completed_at"] = datetime.utcnow()
    await session.execute(update(DirectoryUploadJob).where(DirectoryUploadJob.id == job_id).values(**values))


async def count_entries_by_status(
    session: AsyncSession,
    job_id: object,
    *statuses: object,
) -> int:
    stmt = select(func.count(DirectoryUploadEntry.id)).where(
        DirectoryUploadEntry.directory_upload_id == job_id
    )
    if statuses:
        stmt = stmt.where(DirectoryUploadEntry.status.in_(statuses))
    result = await session.execute(stmt)
    return result.scalar_one() or 0
