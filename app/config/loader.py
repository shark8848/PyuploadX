"""Configuration loading: defaults < YAML < environment variables < CLI args."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from app.config.models import Settings

_ENV_PREFIX = "UPLOAD_"
_ENV_SEPARATOR = "__"


def _coerce(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return value
    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def env_overrides() -> dict[str, Any]:
    """Build a nested dict from UPLOAD_SECTION__FIELD style environment variables."""
    overrides: dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        parts = key[len(_ENV_PREFIX) :].lower().split(_ENV_SEPARATOR)
        cursor = overrides
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = _coerce(value)
    return overrides


def load_yaml(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {config_path} must contain a YAML mapping")
    return data


def load_settings(config_path: str | Path | None = None, **cli_overrides: Any) -> Settings:
    """Load settings with priority: defaults < YAML < env < CLI overrides."""
    raw: dict[str, Any] = {}
    yaml_data = load_yaml(config_path)
    if yaml_data:
        raw = _deep_merge(raw, yaml_data)
    env_data = env_overrides()
    if env_data:
        raw = _deep_merge(raw, env_data)
    if cli_overrides:
        raw = _deep_merge(raw, cli_overrides)
    return Settings.model_validate(raw)
