"""Idempotency-Key support backed by the idempotency_records table."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IdempotencyRecord


@dataclass(frozen=True)
class IdempotencyHit:
    status_code: int
    body: dict[str, Any]


def request_hash(operation: str, payload: dict[str, Any] | None) -> str:
    digest = hashlib.sha256()
    digest.update(operation.encode("utf-8"))
    if payload is not None:
        digest.update(b"\x00")
        digest.update(json.dumps(payload, sort_keys=True, default=str).encode("utf-8"))
    return digest.hexdigest()


async def get_record(
    session: AsyncSession,
    tenant_id: str,
    operation: str,
    key: str,
) -> IdempotencyRecord | None:
    result = await session.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    return result.scalar_one_or_none()


async def store_record(
    session: AsyncSession,
    tenant_id: str,
    operation: str,
    key: str,
    request_hash_value: str,
    status_code: int,
    body: dict[str, Any],
    expires_at: Any,
) -> None:
    session.add(
        IdempotencyRecord(
            tenant_id=tenant_id,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash_value,
            response_status=status_code,
            response_body=body,
            expires_at=expires_at,
        )
    )


async def expire_records(session: AsyncSession, now: Any) -> int:
    result = await session.execute(
        delete(IdempotencyRecord).where(IdempotencyRecord.expires_at <= now)
    )
    return result.rowcount or 0
