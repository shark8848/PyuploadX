"""Upload session repository with row-locking for complete/abort (docs 20.2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UploadSession, UploadStatus


async def get_upload(
    session: AsyncSession,
    upload_id: object,
    *,
    tenant_id: str | None = None,
    for_update: bool = False,
) -> UploadSession | None:
    stmt = select(UploadSession).where(UploadSession.id == upload_id)
    if tenant_id is not None:
        stmt = stmt.where(UploadSession.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_status(
    session: AsyncSession,
    upload_id: object,
    status: UploadStatus,
    *,
    completed_file_id: object | None = None,
) -> None:
    values: dict = {"status": status, "updated_at": datetime.utcnow()}
    if completed_file_id is not None:
        values["completed_file_id"] = completed_file_id
    await session.execute(update(UploadSession).where(UploadSession.id == upload_id).values(**values))


async def touch_activity(session: AsyncSession, upload_id: object) -> None:
    await session.execute(
        update(UploadSession)
        .where(UploadSession.id == upload_id)
        .values(last_activity_at=datetime.utcnow(), updated_at=datetime.utcnow())
    )
