"""File lifecycle service per docs_product-design.md sections 14 and 16.5."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.models import Settings
from app.core.auth import Identity
from app.core.errors import (
    ApiError,
    FileUnderLegalHoldError,
    InvalidLifecyclePolicyError,
)
from app.db import repositories
from app.db.models import FileObject, LifecycleEvent
from app.lifecycle.policy import compute_effective_lifecycle


def _now() -> datetime:
    return datetime.now(UTC)


class LifecycleService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _effective(
        self,
        requested: dict[str, Any] | None,
        completed_at: datetime,
    ) -> dict[str, Any]:
        return compute_effective_lifecycle(
            requested=requested,
            server_default=self.settings.lifecycle.default_policy.model_dump(),
            allow_client_override=self.settings.lifecycle.policy.allow_client_override,
            permanent_allowed=self.settings.lifecycle.policy.permanent_allowed,
            minimum_ttl_seconds=self.settings.lifecycle.policy.minimum_ttl_seconds,
            maximum_ttl_seconds=self.settings.lifecycle.policy.maximum_ttl_seconds,
            allowed_modes=self.settings.lifecycle.policy.allowed_modes,
            allowed_actions=self.settings.lifecycle.policy.allowed_actions,
            completed_at=completed_at,
        )

    def _apply(self, file_obj: FileObject, effective: dict[str, Any]) -> None:
        file_obj.lifecycle_mode = effective["mode"]
        file_obj.lifecycle_action = effective["action"]
        file_obj.ttl_seconds = effective.get("ttl_seconds")
        file_obj.expires_at = (
            datetime.fromisoformat(effective["expires_at"]) if effective.get("expires_at") else None
        )
        file_obj.next_action_at = file_obj.expires_at if effective["action"] != "none" else None

    async def get_lifecycle(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
    ) -> dict[str, Any]:
        file_obj = await repositories.file_repository.get_file(session, file_id, tenant_id=identity.tenant_id)
        if file_obj is None:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        return {
            "mode": file_obj.lifecycle_mode,
            "action": file_obj.lifecycle_action,
            "ttl_seconds": file_obj.ttl_seconds,
            "expires_at": file_obj.expires_at.isoformat() if file_obj.expires_at else None,
            "status": file_obj.lifecycle_status.value,
        }

    async def update_lifecycle(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
        requested: dict[str, Any],
    ) -> dict[str, Any]:
        file_obj = await repositories.file_repository.get_file(
            session, file_id, tenant_id=identity.tenant_id, for_update=True
        )
        if file_obj is None:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        if file_obj.legal_hold:
            raise FileUnderLegalHoldError()
        effective = self._effective(requested, file_obj.completed_at)
        self._apply(file_obj, effective)
        file_obj.lifecycle_source = "client"
        session.add(
            LifecycleEvent(
                tenant_id=identity.tenant_id,
                file_id=file_obj.id,
                event_type="lifecycle.updated",
                from_status=file_obj.lifecycle_status.value,
                to_status=file_obj.lifecycle_status.value,
                details={"effective": effective},
            )
        )
        await session.flush()
        return self._lifecycle_dict(file_obj)

    def _lifecycle_dict(self, file_obj: FileObject) -> dict[str, Any]:
        return {
            "mode": file_obj.lifecycle_mode,
            "action": file_obj.lifecycle_action,
            "ttl_seconds": file_obj.ttl_seconds,
            "expires_at": file_obj.expires_at.isoformat() if file_obj.expires_at else None,
            "status": file_obj.lifecycle_status.value,
        }

    async def extend(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
        extend_seconds: int,
    ) -> dict[str, Any]:
        file_obj = await repositories.file_repository.get_file(
            session, file_id, tenant_id=identity.tenant_id, for_update=True
        )
        if file_obj is None:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        if file_obj.lifecycle_mode in ("permanent", "expires_at"):
            raise InvalidLifecyclePolicyError(f"cannot extend {file_obj.lifecycle_mode} lifecycle")
        if extend_seconds <= 0:
            raise InvalidLifecyclePolicyError("extend_seconds must be positive")
        base = file_obj.expires_at or _now()
        requested = {
            "mode": file_obj.lifecycle_mode,
            "action": file_obj.lifecycle_action,
            "ttl_seconds": file_obj.ttl_seconds,
            "expires_at": (base + timedelta(seconds=extend_seconds)).isoformat(),
        }
        effective = self._effective(requested, file_obj.completed_at)
        self._apply(file_obj, effective)
        session.add(
            LifecycleEvent(
                tenant_id=identity.tenant_id,
                file_id=file_obj.id,
                event_type="lifecycle.extended",
                from_status=file_obj.lifecycle_status.value,
                to_status=file_obj.lifecycle_status.value,
                details={"extend_seconds": extend_seconds, "effective": effective},
            )
        )
        await session.flush()
        return self._lifecycle_dict(file_obj)

    async def make_permanent(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
    ) -> dict[str, Any]:
        if not self.settings.lifecycle.policy.permanent_allowed:
            raise InvalidLifecyclePolicyError("permanent lifecycle is not allowed by server policy")
        file_obj = await repositories.file_repository.get_file(
            session, file_id, tenant_id=identity.tenant_id, for_update=True
        )
        if file_obj is None:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        if file_obj.legal_hold:
            raise FileUnderLegalHoldError()
        file_obj.lifecycle_mode = "permanent"
        file_obj.lifecycle_action = "none"
        file_obj.ttl_seconds = None
        file_obj.expires_at = None
        file_obj.next_action_at = None
        session.add(
            LifecycleEvent(
                tenant_id=identity.tenant_id,
                file_id=file_obj.id,
                event_type="lifecycle.make_permanent",
                from_status=file_obj.lifecycle_status.value,
                to_status=file_obj.lifecycle_status.value,
            )
        )
        await session.flush()
        return self._lifecycle_dict(file_obj)

    async def set_legal_hold(
        self,
        session: AsyncSession,
        identity: Identity,
        file_id: uuid.UUID,
        hold: bool,
    ) -> dict[str, Any]:
        file_obj = await repositories.file_repository.get_file(
            session, file_id, tenant_id=identity.tenant_id, for_update=True
        )
        if file_obj is None:
            raise ApiError("FILE_NOT_FOUND", f"File {file_id} does not exist.", status_code=404)
        file_obj.legal_hold = hold
        session.add(
            LifecycleEvent(
                tenant_id=identity.tenant_id,
                file_id=file_obj.id,
                event_type="legal_hold.set" if hold else "legal_hold.released",
                from_status=file_obj.lifecycle_status.value,
                to_status=file_obj.lifecycle_status.value,
            )
        )
        await session.flush()
        return {"legal_hold": file_obj.legal_hold, "file_id": str(file_obj.id)}
