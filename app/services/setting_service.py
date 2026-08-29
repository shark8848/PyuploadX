"""Runtime storage settings service backed by the app_settings table."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db import repositories

KEY_DEFAULT_BUCKET = "storage.default_bucket"
KEY_PRESIGN_DEFAULT = "storage.presign.default_expires_seconds"
MIN_PRESIGN_SECONDS = 60


class SettingService:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def get_default_bucket(self, session: AsyncSession) -> str:
        overrides = await repositories.setting_repository.get_many(session, [KEY_DEFAULT_BUCKET])
        return overrides.get(KEY_DEFAULT_BUCKET) or self.settings.storage.default_bucket

    async def get_presign_default_seconds(self, session: AsyncSession) -> int:
        overrides = await repositories.setting_repository.get_many(session, [KEY_PRESIGN_DEFAULT])
        raw = overrides.get(KEY_PRESIGN_DEFAULT)
        if raw is None:
            return self.settings.presign.default_expires_seconds
        try:
            return int(raw)
        except ValueError:
            return self.settings.presign.default_expires_seconds

    async def get_effective(self, session: AsyncSession) -> dict[str, object]:
        return {
            "default_bucket": await self.get_default_bucket(session),
            "presign_default_expires_seconds": await self.get_presign_default_seconds(session),
        }

    async def update(
        self,
        session: AsyncSession,
        payload: dict,
        allowed_buckets: list[str],
    ) -> dict[str, object]:
        storage = payload.get("storage") if isinstance(payload, dict) else None
        if not isinstance(storage, dict):
            raise ApiError("INVALID_SETTINGS", "settings.storage is required.", status_code=422)

        default_bucket = storage.get("default_bucket")
        if not isinstance(default_bucket, str) or not default_bucket.strip():
            raise ApiError("INVALID_SETTINGS", "default_bucket is required.", status_code=422)
        default_bucket = default_bucket.strip()
        if default_bucket not in allowed_buckets:
            raise ApiError(
                "INVALID_SETTINGS",
                f"Bucket {default_bucket!r} is not allowed.",
                status_code=422,
            )
        await repositories.setting_repository.set_value(session, KEY_DEFAULT_BUCKET, default_bucket)

        presign = storage.get("presign_default_expires_seconds")
        if presign is not None:
            try:
                seconds = int(presign)
            except (TypeError, ValueError) as exc:
                raise ApiError(
                    "INVALID_SETTINGS",
                    "presign_default_expires_seconds must be an integer.",
                    status_code=422,
                ) from exc
            maximum = self.settings.presign.maximum_expires_seconds
            if not (MIN_PRESIGN_SECONDS <= seconds <= maximum):
                raise ApiError(
                    "INVALID_SETTINGS",
                    f"presign_default_expires_seconds must be within [{MIN_PRESIGN_SECONDS}, {maximum}].",
                    status_code=422,
                )
            await repositories.setting_repository.set_value(session, KEY_PRESIGN_DEFAULT, str(seconds))
        await session.flush()
        return await self.get_effective(session)
