"""Runtime settings service backed by the app_settings table.

Writable groups: storage (default bucket / presign expiry), uploads
(max size, direct threshold, default mode, default part size, session
expiry) and lifecycle (default policy). Storage backend connection
parameters (backend type, S3 keys, endpoints) are bootstrap config and
stay read-only; see docs_product-design.md section 19.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db import repositories

KEY_DEFAULT_BUCKET = "storage.default_bucket"
KEY_PRESIGN_DEFAULT = "storage.presign.default_expires_seconds"
KEY_MAX_FILE_SIZE = "uploads.maximum_file_size_bytes"
KEY_DIRECT_THRESHOLD = "uploads.direct_upload_threshold_bytes"
KEY_DEFAULT_MODE = "uploads.default_mode"
KEY_DEFAULT_PART_SIZE = "uploads.multipart.default_part_size_bytes"
KEY_SESSION_EXPIRY = "uploads.session.expires_after_seconds"
KEY_LIFECYCLE_DEFAULT = "lifecycle.default_policy"

MIN_PRESIGN_SECONDS = 60
MIN_SESSION_SECONDS = 60


def _int_override(raw: str | None, fallback: int) -> int:
    if raw is None:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


class SettingService:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def _overrides(self, session: AsyncSession) -> dict[str, str]:
        return await repositories.setting_repository.get_many(
            session,
            [
                KEY_DEFAULT_BUCKET,
                KEY_PRESIGN_DEFAULT,
                KEY_MAX_FILE_SIZE,
                KEY_DIRECT_THRESHOLD,
                KEY_DEFAULT_MODE,
                KEY_DEFAULT_PART_SIZE,
                KEY_SESSION_EXPIRY,
                KEY_LIFECYCLE_DEFAULT,
            ],
        )

    async def get_default_bucket(self, session: AsyncSession) -> str:
        overrides = await self._overrides(session)
        return overrides.get(KEY_DEFAULT_BUCKET) or self.settings.storage.default_bucket

    async def get_presign_default_seconds(self, session: AsyncSession) -> int:
        overrides = await self._overrides(session)
        return _int_override(overrides.get(KEY_PRESIGN_DEFAULT), self.settings.presign.default_expires_seconds)

    async def get_max_file_size(self, session: AsyncSession) -> int:
        overrides = await self._overrides(session)
        return _int_override(overrides.get(KEY_MAX_FILE_SIZE), self.settings.uploads.file_size.maximum_bytes)

    async def get_direct_threshold(self, session: AsyncSession) -> int:
        overrides = await self._overrides(session)
        return _int_override(overrides.get(KEY_DIRECT_THRESHOLD), self.settings.uploads.direct_upload_threshold_bytes)

    async def get_default_mode(self, session: AsyncSession) -> str:
        overrides = await self._overrides(session)
        return overrides.get(KEY_DEFAULT_MODE) or self.settings.uploads.default_mode

    async def get_default_part_size(self, session: AsyncSession) -> int:
        overrides = await self._overrides(session)
        return _int_override(overrides.get(KEY_DEFAULT_PART_SIZE), self.settings.uploads.multipart.default_part_size_bytes)

    async def get_session_expiry(self, session: AsyncSession) -> int:
        overrides = await self._overrides(session)
        return _int_override(overrides.get(KEY_SESSION_EXPIRY), self.settings.uploads.session.expires_after_seconds)

    async def get_lifecycle_default(self, session: AsyncSession) -> dict[str, Any]:
        overrides = await self._overrides(session)
        raw = overrides.get(KEY_LIFECYCLE_DEFAULT)
        if raw is None:
            return self.settings.lifecycle.default_policy.model_dump()
        try:
            value = __import__("json").loads(raw)
        except ValueError:
            return self.settings.lifecycle.default_policy.model_dump()
        if not isinstance(value, dict):
            return self.settings.lifecycle.default_policy.model_dump()
        base = self.settings.lifecycle.default_policy.model_dump()
        base.update({key: value[key] for key in ("mode", "action", "ttl_seconds") if key in value})
        return base

    async def get_effective(self, session: AsyncSession) -> dict[str, Any]:
        uploads = self.settings.uploads
        lifecycle = self.settings.lifecycle
        return {
            "storage": {
                "default_bucket": await self.get_default_bucket(session),
                "presign_default_expires_seconds": await self.get_presign_default_seconds(session),
                "maximum_expires_seconds": self.settings.presign.maximum_expires_seconds,
            },
            "uploads": {
                "maximum_file_size_bytes": await self.get_max_file_size(session),
                "direct_upload_threshold_bytes": await self.get_direct_threshold(session),
                "default_mode": await self.get_default_mode(session),
                "multipart": {
                    "default_part_size_bytes": await self.get_default_part_size(session),
                    "minimum_part_size_bytes": uploads.multipart.minimum_part_size_bytes,
                    "maximum_part_size_bytes": uploads.multipart.maximum_part_size_bytes,
                    "maximum_parts": uploads.multipart.maximum_parts,
                },
                "session": {
                    "expires_after_seconds": await self.get_session_expiry(session),
                    "maximum_lifetime_seconds": uploads.session.maximum_lifetime_seconds,
                },
            },
            "lifecycle": {
                "default_policy": await self.get_lifecycle_default(session),
                "allowed_modes": lifecycle.policy.allowed_modes,
                "allowed_actions": lifecycle.policy.allowed_actions,
                "permanent_allowed": lifecycle.policy.permanent_allowed,
                "minimum_ttl_seconds": lifecycle.policy.minimum_ttl_seconds,
                "maximum_ttl_seconds": lifecycle.policy.maximum_ttl_seconds,
            },
        }

    async def update(
        self,
        session: AsyncSession,
        payload: dict,
        allowed_buckets: list[str],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ApiError("INVALID_SETTINGS", "settings body must be an object.", status_code=422)

        storage = payload.get("storage") if isinstance(payload.get("storage"), dict) else None
        uploads = payload.get("uploads") if isinstance(payload.get("uploads"), dict) else None
        lifecycle = payload.get("lifecycle") if isinstance(payload.get("lifecycle"), dict) else None
        if storage is None and uploads is None and lifecycle is None:
            raise ApiError(
                "INVALID_SETTINGS",
                "At least one of settings.storage / settings.uploads / settings.lifecycle is required.",
                status_code=422,
            )

        if storage is not None:
            await self._update_storage(session, storage, allowed_buckets)
        if uploads is not None:
            await self._update_uploads(session, uploads)
        if lifecycle is not None:
            await self._update_lifecycle(session, lifecycle)

        await session.flush()
        return await self.get_effective(session)

    async def _update_storage(
        self,
        session: AsyncSession,
        storage: dict,
        allowed_buckets: list[str],
    ) -> None:
        default_bucket = storage.get("default_bucket")
        if default_bucket is not None:
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
            seconds = self._int_field("presign_default_expires_seconds", presign)
            maximum = self.settings.presign.maximum_expires_seconds
            if not (MIN_PRESIGN_SECONDS <= seconds <= maximum):
                raise ApiError(
                    "INVALID_SETTINGS",
                    f"presign_default_expires_seconds must be within [{MIN_PRESIGN_SECONDS}, {maximum}].",
                    status_code=422,
                )
            await repositories.setting_repository.set_value(session, KEY_PRESIGN_DEFAULT, str(seconds))

    async def _update_uploads(self, session: AsyncSession, uploads: dict) -> None:
        multipart = uploads.get("multipart") if isinstance(uploads.get("multipart"), dict) else None
        session_cfg = uploads.get("session") if isinstance(uploads.get("session"), dict) else None
        min_part = self.settings.uploads.multipart.minimum_part_size_bytes
        max_part = self.settings.uploads.multipart.maximum_part_size_bytes

        max_size = uploads.get("maximum_file_size_bytes")
        if max_size is not None:
            value = self._int_field("maximum_file_size_bytes", max_size)
            if value <= 0:
                raise ApiError("INVALID_SETTINGS", "maximum_file_size_bytes must be positive.", status_code=422)
            await repositories.setting_repository.set_value(session, KEY_MAX_FILE_SIZE, str(value))

        threshold = uploads.get("direct_upload_threshold_bytes")
        if threshold is not None:
            value = self._int_field("direct_upload_threshold_bytes", threshold)
            if value < 0:
                raise ApiError("INVALID_SETTINGS", "direct_upload_threshold_bytes must be non-negative.", status_code=422)
            await repositories.setting_repository.set_value(session, KEY_DIRECT_THRESHOLD, str(value))

        mode = uploads.get("default_mode")
        if mode is not None:
            allowed = ("automatic", "proxy", "presigned")
            if mode not in allowed:
                raise ApiError(
                    "INVALID_SETTINGS",
                    f"default_mode must be one of {allowed}.",
                    status_code=422,
                )
            await repositories.setting_repository.set_value(session, KEY_DEFAULT_MODE, str(mode))

        if multipart is not None and "default_part_size_bytes" in multipart:
            value = self._int_field("default_part_size_bytes", multipart["default_part_size_bytes"])
            if not (min_part <= value <= max_part):
                raise ApiError(
                    "INVALID_SETTINGS",
                    f"default_part_size_bytes must be within [{min_part}, {max_part}].",
                    status_code=422,
                )
            await repositories.setting_repository.set_value(session, KEY_DEFAULT_PART_SIZE, str(value))

        if session_cfg is not None and "expires_after_seconds" in session_cfg:
            value = self._int_field("expires_after_seconds", session_cfg["expires_after_seconds"])
            maximum = self.settings.uploads.session.maximum_lifetime_seconds
            if not (MIN_SESSION_SECONDS <= value <= maximum):
                raise ApiError(
                    "INVALID_SETTINGS",
                    f"expires_after_seconds must be within [{MIN_SESSION_SECONDS}, {maximum}].",
                    status_code=422,
                )
            await repositories.setting_repository.set_value(session, KEY_SESSION_EXPIRY, str(value))

    async def _update_lifecycle(self, session: AsyncSession, lifecycle: dict) -> None:
        policy = lifecycle.get("default_policy")
        if policy is None or not isinstance(policy, dict):
            raise ApiError("INVALID_SETTINGS", "lifecycle.default_policy is required.", status_code=422)
        rules = self.settings.lifecycle.policy
        mode = policy.get("mode")
        action = policy.get("action")
        ttl_seconds = policy.get("ttl_seconds")
        if mode is not None and mode not in rules.allowed_modes:
            raise ApiError(
                "INVALID_SETTINGS",
                f"default_policy.mode must be one of {rules.allowed_modes}.",
                status_code=422,
            )
        if action is not None and action not in rules.allowed_actions:
            raise ApiError(
                "INVALID_SETTINGS",
                f"default_policy.action must be one of {rules.allowed_actions}.",
                status_code=422,
            )
        if ttl_seconds is not None:
            value = self._int_field("ttl_seconds", ttl_seconds)
            if not (rules.minimum_ttl_seconds <= value <= rules.maximum_ttl_seconds):
                raise ApiError(
                    "INVALID_SETTINGS",
                    f"ttl_seconds must be within [{rules.minimum_ttl_seconds}, {rules.maximum_ttl_seconds}].",
                    status_code=422,
                )
            ttl_seconds = value
        current = await self.get_lifecycle_default(session)
        current.update({key: value for key, value in (("mode", mode), ("action", action), ("ttl_seconds", ttl_seconds)) if value is not None})
        await repositories.setting_repository.set_value(
            session, KEY_LIFECYCLE_DEFAULT, __import__("json").dumps(current)
        )

    @staticmethod
    def _int_field(name: str, value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ApiError("INVALID_SETTINGS", f"{name} must be an integer.", status_code=422) from exc
