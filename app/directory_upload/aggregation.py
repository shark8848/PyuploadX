"""Directory upload progress aggregation."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DirectoryUploadEntry, DirectoryUploadJob, EntryStatus


async def aggregate_progress(session: AsyncSession, job_id: object) -> None:
    """Aggregate entry counts into the directory job row."""
    counts = await session.execute(
        select(
            func.count(DirectoryUploadEntry.id),
            func.sum(DirectoryUploadEntry.size_bytes).label("bytes"),
            func.count().filter(DirectoryUploadEntry.status == EntryStatus.uploaded).label("uploaded"),
            func.count().filter(DirectoryUploadEntry.status == EntryStatus.failed).label("failed"),
            func.count().filter(DirectoryUploadEntry.status == EntryStatus.skipped).label("skipped"),
        ).where(DirectoryUploadEntry.directory_upload_id == job_id)
    )
    row = counts.one()
    total_entries = row[0] or 0
    total_bytes = row[1] or 0
    uploaded_files = row[2] or 0
    failed_files = row[3] or 0
    skipped_files = row[4] or 0
    await session.execute(
        update(DirectoryUploadJob)
        .where(DirectoryUploadJob.id == job_id)
        .values(
            total_entries=total_entries,
            total_bytes=total_bytes,
            uploaded_files=uploaded_files,
            failed_files=failed_files,
            skipped_files=skipped_files,
        )
    )
