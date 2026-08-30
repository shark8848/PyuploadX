"""Shared fixtures. Environment must be configured before importing app modules."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

TEST_STATE: dict[str, str] = {}

# SDK 独立打包后不再随服务端安装；测试直接从源码导入（sdk/ 下即 pyuploadx 包）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))


def _configure_env() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="pyuploadx-test-"))
    storage_root = tmp / "storage"
    multipart_root = tmp / "storage" / ".multipart"
    os.environ["UPLOAD_API_KEYS"] = '{"acme/alice": ["test-key-1"]}'
    os.environ["UPLOAD_DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp / 'test.db'}"
    os.environ["UPLOAD_REDIS__ENABLED"] = "false"
    os.environ["UPLOAD_STORAGE__BACKEND"] = "local"
    os.environ["UPLOAD_STORAGE__LOCAL__ROOT_PATH"] = str(storage_root)
    os.environ["UPLOAD_STORAGE__LOCAL__MULTIPART_PATH"] = str(multipart_root)
    os.environ["UPLOAD_CLUSTER__ENABLED"] = "false"
    os.environ["UPLOAD_PORTAL__ORIGINS"] = '["http://localhost:5173"]'
    os.environ["UPLOAD_PERMANENT_LINK_SECRET"] = "test-permanent-link-secret"
    os.environ["UPLOAD_UPLOADS__MULTIPART__MINIMUM_PART_SIZE_BYTES"] = "1"
    os.environ["UPLOAD_UPLOADS__MULTIPART__DEFAULT_PART_SIZE_BYTES"] = str(5 * 1024 * 1024)
    TEST_STATE["tmp"] = str(tmp)
    return tmp


@pytest.fixture(scope="session")
def app():
    tmp = _configure_env()
    from app.main import create_app

    application = create_app()
    yield application
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": "test-key-1"}


@pytest.fixture()
def storage_tmp(app) -> Path:
    from app.api.dependencies import AppState

    state: AppState = app.state.state
    return Path(state.settings.storage.local.root_path)
