"""Runtime settings repository (app_settings table)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSetting


async def get(session: AsyncSession, key: str) -> AppSetting | None:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    return result.scalar_one_or_none()


async def get_many(session: AsyncSession, keys: list[str]) -> dict[str, str]:
    result = await session.execute(select(AppSetting).where(AppSetting.key.in_(keys)))
    return {row.key: row.value for row in result.scalars().all()}


async def set_value(session: AsyncSession, key: str, value: str) -> None:
    existing = await get(session, key)
    if existing is None:
        session.add(AppSetting(id=uuid.uuid4(), key=key, value=value))
    else:
        existing.value = value
    await session.flush()
