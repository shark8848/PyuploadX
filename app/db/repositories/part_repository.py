"""Upload part repository with upsert per docs section 20.4."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PartStatus, UploadPart


async def upsert_part(
    session: AsyncSession,
    *,
    upload_id: object,
    part_number: int,
    offset_bytes: int,
    size_bytes: int,
    etag: str | None,
    checksum_sha256: str | None,
    status: PartStatus,
) -> None:
    now = datetime.utcnow()
    values = {
        "upload_id": upload_id,
        "part_number": part_number,
        "offset_bytes": offset_bytes,
        "size_bytes": size_bytes,
        "etag": etag,
        "checksum_sha256": checksum_sha256,
        "status": status,
        "updated_at": now,
    }
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    if dialect == "postgresql":
        stmt = pg_insert(UploadPart).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["upload_id", "part_number"],
            set_={
                "etag": stmt.excluded.etag,
                "size_bytes": stmt.excluded.size_bytes,
                "status": stmt.excluded.status,
                "checksum_sha256": stmt.excluded.checksum_sha256,
                "updated_at": stmt.excluded.updated_at,
            },
        )
    else:
        existing = await session.execute(
            select(UploadPart.id).where(
                UploadPart.upload_id == upload_id,
                UploadPart.part_number == part_number,
            )
        )
        if existing.scalar_one_or_none() is not None:
            stmt = (
                update(UploadPart)
                .where(
                    UploadPart.upload_id == upload_id,
                    UploadPart.part_number == part_number,
                )
                .values(**values)
            )
        else:
            session.add(UploadPart(**values))
            return
    await session.execute(stmt)


async def list_parts_for_upload(
    session: AsyncSession,
    upload_id: object,
) -> list[UploadPart]:
    result = await session.execute(
        select(UploadPart)
        .where(UploadPart.upload_id == upload_id)
        .order_by(UploadPart.part_number)
    )
    return list(result.scalars().all())
