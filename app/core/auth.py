"""API key authentication per docs_product-design.md section 22.1."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.core.errors import AuthenticationError


@dataclass(frozen=True)
class Identity:
    tenant_id: str
    principal_id: str


class ApiKeyAuthenticator:
    """Resolve an API key to a tenant/principal identity.

    The environment variable UPLOAD_API_KEYS holds either:
      - a JSON object mapping "tenant/principal" -> [keys], or
      - a JSON array of raw keys (identity becomes "default/default").
    """

    def __init__(self, keys_from_env: str = "UPLOAD_API_KEYS") -> None:
        self._keys: dict[str, Identity] = {}
        raw = os.environ.get(keys_from_env)
        if raw:
            self._load(raw)

    def _load(self, raw: str) -> None:
        data: Any = json.loads(raw)
        if isinstance(data, dict):
            for scope, keys in data.items():
                if isinstance(keys, str):
                    keys = [keys]
                tenant, _, principal = scope.partition("/")
                identity = Identity(tenant_id=tenant, principal_id=principal or "default")
                for key in keys:
                    self._keys[key] = identity
        elif isinstance(data, list):
            for key in data:
                self._keys[key] = Identity(tenant_id="default", principal_id="default")

    def authenticate(self, api_key: str | None) -> Identity:
        if not api_key:
            raise AuthenticationError()
        identity = self._keys.get(api_key)
        if identity is None:
            raise AuthenticationError()
        return identity

    def __len__(self) -> int:
        return len(self._keys)
