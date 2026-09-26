"""File object repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FileObject, FileStatus

# Sortable fields for `GET /v1/files` (docs_product-design.md section 16.2); keys are the
# API field names, with `name` kept as the legacy alias for `object_key` (the default sort).
SORTABLE_COLUMNS: dict[str, Any] = {
    "object_key": FileObject.object_key,
    "bucket": FileObject.bucket,
    "size_bytes": FileObject.size_bytes,
    "content_type": FileObject.content_type,
    "status": FileObject.status,
    "expires_at": FileObject.expires_at,
    "created_at": FileObject.created_at,
}

# Per-field default direction when `sort_order` is omitted: `created_at` keeps its historical
# newest-first order, everything else is ascending.
DEFAULT_SORT_ORDER: dict[str, str] = {"created_at": "desc"}

# A null `expires_at` means a permanent file: keep those last in both directions, since DESC
# would otherwise float NULLs to the top.
NULLS_LAST_SORT_FIELDS = frozenset({"expires_at"})


def normalize_sort_field(order_by: str) -> str:
    """Map the legacy `name` alias onto the API field name."""
    return "object_key" if order_by == "name" else order_by


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
    order: str | None = None,
) -> tuple[list[FileObject], int]:
    """Page over file objects for a tenant with optional filters and sorting.

    `order_by` accepts the fields of `SORTABLE_COLUMNS` (plus the `name` alias);
    `order` is `asc`/`desc`, defaulting per field via `DEFAULT_SORT_ORDER`.
    The sort is always deterministic (object_key then id as tie-breakers) so that
    offset paging cannot repeat or skip rows.
    """
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
    field = normalize_sort_field(order_by)
    column = SORTABLE_COLUMNS.get(field, FileObject.object_key)
    direction = order if order in ("asc", "desc") else DEFAULT_SORT_ORDER.get(field, "asc")
    primary = column.desc() if direction == "desc" else column.asc()
    if field in NULLS_LAST_SORT_FIELDS:
        primary = primary.nulls_last()
    ordering = [primary]
    if field != "object_key":
        ordering.append(FileObject.object_key.asc())
    ordering.append(FileObject.id.asc())
    stmt = stmt.order_by(*ordering)
    result = await session.execute(stmt.offset(offset).limit(limit))
    return list(result.scalars().all()), total
