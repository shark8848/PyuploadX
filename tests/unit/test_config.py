"""Config loading and validation tests (docs section 19, 29.1)."""

from __future__ import annotations

import os


def test_env_nested_override(monkeypatch):
    monkeypatch.setenv("UPLOAD_SERVER__PORT", "8080")
    monkeypatch.setenv("UPLOAD_UPLOADS__MULTIPART__DEFAULT_PART_SIZE_BYTES", "10485760")
    monkeypatch.delenv("UPLOAD_DATABASE_URL", raising=False)
    from app.config.loader import load_settings

    settings = load_settings()
    assert settings.server.port == 8080
    assert settings.uploads.multipart.default_part_size_bytes == 10485760


def test_validation_rejects_sqlite_in_cluster_mode():
    os.environ["UPLOAD_DATABASE_URL"] = "sqlite+aiosqlite:///x.db"
    os.environ["UPLOAD_CLUSTER__ENABLED"] = "true"
    from app.config.loader import load_settings
    from app.config.validation import validate_settings

    settings = load_settings()
    result = validate_settings(settings)
    assert not result.ok
    assert any("SQLite" in error for error in result.errors)


def test_secret_resolution(monkeypatch):
    monkeypatch.setenv("UPLOAD_DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/uploads")
    monkeypatch.setenv("UPLOAD_CLUSTER__ENABLED", "false")
    monkeypatch.setenv("UPLOAD_STORAGE__BACKEND", "s3")
    monkeypatch.setenv("UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("S3_SECRET_KEY", "sk")
    from app.config.loader import load_settings
    from app.config.validation import validate_settings

    settings = load_settings()
    assert settings.database.url == "postgresql+asyncpg://user:pass@db:5432/uploads"
    assert settings.storage.s3.access_key == "ak"
    result = validate_settings(settings)
    assert result.ok
