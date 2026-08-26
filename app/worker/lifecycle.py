"""Lifecycle worker loop per docs_product-design.md section 14.6."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import metrics
from app.core.errors import FileUnderLegalHoldError
from app.db.models import FileObject, FileStatus, LifecycleEvent, LifecycleStatus
from app.services.webhook_service import enqueue
from app.storage.base import StorageAdapter


logger = logging.getLogger("upload_service.worker.lifecycle")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _process_batch(
    session_factory: async_sessionmaker[AsyncSession],
    storage: StorageAdapter,
    batch_size: int,
) -> int:
    processed = 0
    async with session_factory() as session:
        # FOR UPDATE SKIP LOCKED is Postgres-specific; use a best-effort lock for SQLite.
        result = await session.execute(
            select(FileObject)
            .where(
                FileObject.status == FileStatus.active,
                FileObject.next_action_at <= _now(),
                FileObject.next_action_at.is_not(None),
                FileObject.lifecycle_status == LifecycleStatus.active,
            )
            .order_by(FileObject.next_action_at)
            .limit(batch_size)
        )
        files = list(result.scalars().all())
        for file_obj in files:
            if file_obj.legal_hold:
                session.add(
                    LifecycleEvent(
                        tenant_id=file_obj.tenant_id,
                        file_id=file_obj.id,
                        event_type="lifecycle.blocked",
                        from_status=file_obj.lifecycle_status.value,
                        to_status=file_obj.lifecycle_status.value,
                        reason="legal_hold",
                    )
                )
                continue
            action = file_obj.lifecycle_action
            old_status = file_obj.lifecycle_status
            try:
                if action == "delete":
                    file_obj.lifecycle_status = LifecycleStatus.deleting
                    await session.flush()
                    await storage.delete_object(
                        bucket=file_obj.bucket, object_key=file_obj.object_key
                    )
                    file_obj.status = FileStatus.deleted
                    file_obj.lifecycle_status = LifecycleStatus.deleted
                    file_obj.deleted_at = _now()
                elif action == "notify":
                    file_obj.lifecycle_status = LifecycleStatus.expired
                else:
                    file_obj.next_action_at = None
                metrics.lifecycle_actions_total.labels(action).inc()
                session.add(
                    LifecycleEvent(
                        tenant_id=file_obj.tenant_id,
                        file_id=file_obj.id,
                        event_type=f"lifecycle.{action}",
                        from_status=old_status.value,
                        to_status=file_obj.lifecycle_status.value,
                    )
                )
                await enqueue(
                    session,
                    tenant_id=file_obj.tenant_id,
                    event_type=f"lifecycle.{action}",
                    payload={
                        "file_id": str(file_obj.id),
                        "bucket": file_obj.bucket,
                        "object_key": file_obj.object_key,
                        "action": action,
                    },
                )
                processed += 1
            except Exception:
                metrics.lifecycle_action_failures_total.inc()
                file_obj.delete_attempts += 1
                logger.exception(
                    "lifecycle action failed for file %s",
                    file_obj.id,
                    extra={"extra_fields": {"file_id": str(file_obj.id), "action": action}},
                )
        await session.commit()
    return processed


async def lifecycle_loop(
    session_factory: async_sessionmaker[AsyncSession],
    storage: StorageAdapter,
    *,
    interval_seconds: int = 60,
    batch_size: int = 200,
) -> None:
    while True:
        try:
            processed = await _process_batch(session_factory, storage, batch_size)
            if processed:
                logger.info("lifecycle: processed %d file(s)", processed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("lifecycle loop iteration failed")
        await asyncio.sleep(interval_seconds)
