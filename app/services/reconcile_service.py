"""Storage/DB reconciliation per docs_product-design.md section 21."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.storage.base import StorageAdapter


@dataclass
class ReconcileReport:
    session_id: str
    db_parts: list[int]
    storage_parts: list[int]
    missing_in_db: list[int]
    missing_in_storage: list[int]
    consistent: bool


class ReconcileService:
    def __init__(self, storage: StorageAdapter) -> None:
        self.storage = storage

    async def reconcile_upload(
        self,
        session: AsyncSession,
        upload_id: uuid.UUID,
        *,
        tenant_id: str | None = None,
    ) -> ReconcileReport:
        upload = await repositories.upload_repository.get_upload(session, upload_id, tenant_id=tenant_id)
        if upload is None:
            raise ValueError(f"upload {upload_id} not found")
        db_parts = await repositories.part_repository.list_parts_for_upload(session, upload.id)
        db_numbers = [part.part_number for part in db_parts if part.status.value == "committed"]
        storage_numbers: list[int] = []
        if upload.storage_upload_id and self.storage.capabilities.list_parts:
            stored = await self.storage.list_parts(
                bucket=upload.bucket,
                object_key=upload.object_key,
                storage_upload_id=upload.storage_upload_id,
            )
            storage_numbers = [part.part_number for part in stored]
        db_set, storage_set = set(db_numbers), set(storage_numbers)
        return ReconcileReport(
            session_id=str(upload.id),
            db_parts=db_numbers,
            storage_parts=sorted(storage_set),
            missing_in_db=sorted(storage_set - db_set),
            missing_in_storage=sorted(db_set - storage_set),
            consistent=db_set == storage_set,
        )
