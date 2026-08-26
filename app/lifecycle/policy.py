"""Lifecycle policy adjudication per docs_product-design.md section 14."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.errors import InvalidLifecyclePolicyError, TtlOutOfRangeError
from app.db.models import LifecycleAction, LifecycleMode


def _now() -> datetime:
    return datetime.now(timezone.utc)


def compute_effective_lifecycle(
    *,
    requested: dict[str, Any] | None,
    server_default: dict[str, Any],
    allow_client_override: bool,
    permanent_allowed: bool,
    minimum_ttl_seconds: int,
    maximum_ttl_seconds: int,
    allowed_modes: list[str],
    allowed_actions: list[str],
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    """Merge a client-requested lifecycle with server policy and return the effective policy."""
    requested = dict(requested) if requested else {}
    if not allow_client_override:
        requested = {}

    mode = requested.get("mode") or server_default.get("mode", LifecycleMode.ttl.value)
    action = requested.get("action") or server_default.get("action", LifecycleAction.delete.value)
    ttl_seconds = requested.get("ttl_seconds") or server_default.get("ttl_seconds")
    expires_at = requested.get("expires_at")

    if mode not in allowed_modes:
        raise InvalidLifecyclePolicyError(f"mode {mode!r} is not allowed")
    if action not in allowed_actions:
        raise InvalidLifecyclePolicyError(f"action {action!r} is not allowed")
    if mode == LifecycleMode.permanent.value and not permanent_allowed:
        raise InvalidLifecyclePolicyError("permanent lifecycle is not allowed by server policy")

    effective: dict[str, Any] = {
        "mode": mode,
        "action": action,
        "ttl_seconds": None,
        "expires_at": None,
    }
    base = completed_at or _now()
    if mode == LifecycleMode.ttl.value or mode == LifecycleMode.temporary.value:
        if ttl_seconds is None:
            ttl_seconds = server_default.get("ttl_seconds")
        if ttl_seconds is None:
            raise InvalidLifecyclePolicyError("ttl_seconds is required for ttl lifecycle")
        if not (minimum_ttl_seconds <= ttl_seconds <= maximum_ttl_seconds):
            raise TtlOutOfRangeError(int(ttl_seconds), minimum_ttl_seconds, maximum_ttl_seconds)
        effective["ttl_seconds"] = int(ttl_seconds)
        effective["expires_at"] = (base + timedelta(seconds=int(ttl_seconds))).isoformat()
    elif mode == LifecycleMode.expires_at.value:
        if not expires_at:
            raise InvalidLifecyclePolicyError("expires_at is required for expires_at lifecycle")
        parsed = expires_at
        if isinstance(parsed, str):
            parsed = datetime.fromisoformat(parsed.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        remaining = int((parsed - base).total_seconds())
        if remaining < minimum_ttl_seconds:
            raise TtlOutOfRangeError(remaining, minimum_ttl_seconds, maximum_ttl_seconds)
        effective["ttl_seconds"] = remaining
        effective["expires_at"] = parsed.isoformat()
    elif mode == LifecycleMode.sliding_ttl.value:
        if ttl_seconds is None:
            ttl_seconds = server_default.get("ttl_seconds")
        if ttl_seconds is None:
            raise InvalidLifecyclePolicyError("ttl_seconds is required for sliding_ttl lifecycle")
        if not (minimum_ttl_seconds <= ttl_seconds <= maximum_ttl_seconds):
            raise TtlOutOfRangeError(int(ttl_seconds), minimum_ttl_seconds, maximum_ttl_seconds)
        effective["ttl_seconds"] = int(ttl_seconds)
        effective["expires_at"] = (base + timedelta(seconds=int(ttl_seconds))).isoformat()
    return effective


def apply_lifecycle_to_file(
    *,
    requested_lifecycle: dict[str, Any] | None,
    settings_lifecycle: Any,
    completed_at: datetime,
) -> tuple[dict[str, Any], datetime | None, int | None, str]:
    """Compute effective lifecycle fields for a FileObject row."""
    effective = compute_effective_lifecycle(
        requested=requested_lifecycle,
        server_default=settings_lifecycle.default_policy.model_dump(),
        allow_client_override=settings_lifecycle.policy.allow_client_override,
        permanent_allowed=settings_lifecycle.policy.permanent_allowed,
        minimum_ttl_seconds=settings_lifecycle.policy.minimum_ttl_seconds,
        maximum_ttl_seconds=settings_lifecycle.policy.maximum_ttl_seconds,
        allowed_modes=settings_lifecycle.policy.allowed_modes,
        allowed_actions=settings_lifecycle.policy.allowed_actions,
        completed_at=completed_at,
    )
    expires_at = None
    if effective.get("expires_at"):
        expires_at = datetime.fromisoformat(effective["expires_at"])
    next_action_at = None
    ttl_seconds = effective.get("ttl_seconds")
    if effective["action"] != "none" and expires_at is not None:
        next_action_at = expires_at
    return effective, expires_at, ttl_seconds, effective["mode"]
