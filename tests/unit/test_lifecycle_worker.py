"""Lifecycle worker retry and idempotency regressions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    Base,
    FileObject,
    FileStatus,
    LifecycleAction,
    LifecycleMode,
    LifecycleStatus,
    StorageBackend,
)
from app.storage.s3 import S3StorageAdapter
from app.worker.lifecycle import _process_batch


def _file(lifecycle_status: LifecycleStatus) -> FileObject:
    now = datetime.now(UTC)
    return FileObject(
        id=uuid.uuid4(),
        tenant_id="tenant-test",
        principal_id="principal-test",
        bucket="bucket-test",
        object_key=f"key/{uuid.uuid4()}",
        storage_backend=StorageBackend.local,
        original_filename="test.txt",
        size_bytes=1,
        status=FileStatus.active,
        lifecycle_mode=LifecycleMode.temporary,
        lifecycle_action=LifecycleAction.delete,
        lifecycle_status=lifecycle_status,
        next_action_at=now - timedelta(seconds=1),
        completed_at=now,
        legal_hold=False,
        delete_attempts=0,
    )


async def _factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lifecycle.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_delete_failure_restores_active_and_schedules_retry(tmp_path):
    class FailingStorage:
        async def delete_object(self, *, bucket, object_key):
            raise RuntimeError("s3 unavailable")

    engine, factory = await _factory(tmp_path)
    try:
        row = _file(LifecycleStatus.active)
        async with factory() as session:
            session.add(row)
            await session.commit()

        processed = await _process_batch(factory, FailingStorage(), batch_size=10)

        assert processed == 0
        async with factory() as session:
            stored = await session.get(FileObject, row.id)
            assert stored is not None
            assert stored.lifecycle_status == LifecycleStatus.active
            assert stored.delete_attempts == 1
            assert stored.next_action_at is not None
    finally:
        await engine.dispose()


async def test_historical_deleting_row_is_reprocessed(tmp_path):
    class SuccessfulStorage:
        def __init__(self):
            self.deleted = []

        async def delete_object(self, *, bucket, object_key):
            self.deleted.append((bucket, object_key))

    engine, factory = await _factory(tmp_path)
    try:
        row = _file(LifecycleStatus.deleting)
        async with factory() as session:
            session.add(row)
            await session.commit()

        storage = SuccessfulStorage()
        processed = await _process_batch(factory, storage, batch_size=10)

        assert processed == 1
        assert storage.deleted == [(row.bucket, row.object_key)]
        async with factory() as session:
            stored = await session.get(FileObject, row.id)
            assert stored is not None
            assert stored.status == FileStatus.deleted
            assert stored.lifecycle_status == LifecycleStatus.deleted
            assert stored.deleted_at is not None
    finally:
        await engine.dispose()


async def test_missing_s3_object_is_idempotent_delete():
    class MissingObjectClient:
        def delete_object(self, **_kwargs):
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "DeleteObject")

    adapter = object.__new__(S3StorageAdapter)
    adapter._internal = MissingObjectClient()

    await adapter.delete_object("bucket-test", "already-gone.txt")
