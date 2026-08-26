"""Background cleanup: expired sessions, stale multipart data, idempotency records."""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.models import Settings
from app.core import metrics
from app.core.idempotency import expire_records
from app.db.models import UploadSession, UploadStatus


def _now() -> datetime:
    return datetime.now(UTC)


class CleanupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def expire_upload_sessions(self, session: AsyncSession, batch_size: int = 100) -> int:
        result = await session.execute(
            select(UploadSession.id)
            .where(
                UploadSession.status.in_([UploadStatus.initiated, UploadStatus.uploading]),
                UploadSession.expires_at <= _now(),
            )
            .limit(batch_size)
        )
        ids = [row[0] for row in result.all()]
        if not ids:
            return 0
        await session.execute(
            update(UploadSession)
            .where(UploadSession.id.in_(ids))
            .values(status=UploadStatus.expired, updated_at=_now())
        )
        metrics.upload_expired_total.inc(len(ids))
        for _ in ids:
            metrics.upload_active_sessions.dec()
        await session.flush()
        return len(ids)

    async def cleanup_local_multipart_dirs(self, root: str, max_age_seconds: int = 86400) -> int:
        return await asyncio.to_thread(self._cleanup_local_multipart_dirs_sync, root, max_age_seconds)

    def _cleanup_local_multipart_dirs_sync(self, root: str, max_age_seconds: int) -> int:
        multipart_root = Path(root)
        if not multipart_root.exists():
            return 0
        cutoff = _now() - timedelta(seconds=max_age_seconds)
        cleaned = 0
        for child in multipart_root.iterdir():
            if child.is_dir():
                mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
                    cleaned += 1
        return cleaned

    async def expire_idempotency_records(self, session: AsyncSession, batch_size: int = 100) -> int:
        return await expire_records(session, _now())
