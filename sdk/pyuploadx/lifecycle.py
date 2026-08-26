"""Lifecycle policy builders per docs_product-design.md section 17.3."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class FileLifecycle:
    """Builds a serializable lifecycle policy dict."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def to_dict(self) -> dict[str, Any]:
        return dict(self._payload)

    @classmethod
    def permanent(cls) -> FileLifecycle:
        return cls({"mode": "permanent", "action": "none"})

    @classmethod
    def ttl(cls, duration: timedelta) -> FileLifecycle:
        return cls({"mode": "ttl", "action": "delete", "ttl_seconds": int(duration.total_seconds())})

    @classmethod
    def temporary(cls, duration: timedelta) -> FileLifecycle:
        return cls({"mode": "temporary", "action": "delete", "ttl_seconds": int(duration.total_seconds())})

    @classmethod
    def expires_at(cls, value: datetime) -> FileLifecycle:
        return cls({"mode": "expires_at", "action": "delete", "expires_at": value.isoformat()})

    @classmethod
    def sliding_ttl(cls, duration: timedelta) -> FileLifecycle:
        return cls({"mode": "sliding_ttl", "action": "delete", "ttl_seconds": int(duration.total_seconds())})
