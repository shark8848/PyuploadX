"""Transactional outbox for lifecycle webhooks (docs sections 10.8, 14.6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WebhookOutboxMessage, WebhookStatus


def _now() -> datetime:
    return datetime.now(UTC)


async def enqueue(
    session: AsyncSession,
    *,
    tenant_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        WebhookOutboxMessage(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
            status=WebhookStatus.pending,
            next_attempt_at=_now(),
            attempts=0,
        )
    )


async def deliver_due(
    session: AsyncSession,
    *,
    webhook_url: str | None,
    batch_size: int = 100,
    max_attempts: int = 5,
) -> int:
    """Deliver pending outbox messages to the configured webhook endpoint."""
    if not webhook_url:
        return 0
    result = await session.execute(
        select(WebhookOutboxMessage)
        .where(
            WebhookOutboxMessage.status == WebhookStatus.pending,
            WebhookOutboxMessage.next_attempt_at <= _now(),
        )
        .order_by(WebhookOutboxMessage.created_at)
        .limit(batch_size)
    )
    delivered = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for message in result.scalars().all():
            message.attempts += 1
            try:
                response = await client.post(
                    webhook_url,
                    json={"event_type": message.event_type, "payload": message.payload},
                )
                if response.status_code < 300:
                    message.status = WebhookStatus.delivered
                    delivered += 1
                else:
                    raise RuntimeError(f"webhook returned {response.status_code}")
            except Exception as exc:  # noqa: BLE001
                message.last_error = str(exc)
                if message.attempts >= max_attempts:
                    message.status = WebhookStatus.failed
                else:
                    message.next_attempt_at = _now() + timedelta(
                        seconds=min(2 ** message.attempts, 3600)
                    )
    await session.flush()
    return delivered
