"""Redis 连接面装配：走公共工厂 `ikc_sdk.redis`（docs §19 / §20.6，v0.1.7 起）。

不需要 Redis 服务 —— 只断言 `UPLOAD_*` 环境变量按形态装配出的客户端参数，
以及开关 / 缺 URL / 哨兵缺节点三类分支。
"""

from __future__ import annotations

import os

import pytest

_PREFIXES = ("UPLOAD_REDIS", "UPLOAD_SENTINEL", "UPLOAD_SOCKET")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    """隔离：工厂读 `os.environ` 并兜底读 cwd 的 `.env`，这里清掉本前缀变量并切到空目录。"""
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(_PREFIXES):
            monkeypatch.delenv(key, raising=False)


def test_single_mode_builds_client_with_db(monkeypatch):
    monkeypatch.setenv("UPLOAD_REDIS_MODE", "single")
    monkeypatch.setenv("UPLOAD_REDIS_URL", "redis://:pw@127.0.0.1:6379/7")
    from app.config.models import Settings
    from app.core.redis import build_redis

    client = build_redis(Settings())
    kwargs = client.connection_pool.connection_kwargs
    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("127.0.0.1", 6379, 7)
    assert kwargs["password"] == "pw" and kwargs["decode_responses"] is True


def test_sentinel_mode_builds_master_client(monkeypatch):
    monkeypatch.setenv("UPLOAD_REDIS_MODE", "sentinel")
    monkeypatch.setenv("UPLOAD_SENTINEL_NODES", "10.0.0.1:26380,10.0.0.2:26380")
    monkeypatch.setenv("UPLOAD_SENTINEL_MASTER_NAME", "mymaster")
    monkeypatch.setenv("UPLOAD_SENTINEL_PASSWORD", "masterpw")
    monkeypatch.setenv("UPLOAD_SENTINEL_DB", "7")
    from app.config.models import Settings
    from app.core.redis import build_redis

    kwargs = build_redis(Settings()).connection_pool.connection_kwargs
    assert kwargs["db"] == 7 and kwargs["password"] == "masterpw"


def test_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("UPLOAD_REDIS__ENABLED", "false")
    from app.config.loader import load_settings
    from app.core.redis import build_redis

    assert build_redis(load_settings()) is None


def test_single_mode_without_url_returns_none():
    from app.config.models import Settings
    from app.core.redis import build_redis

    assert build_redis(Settings()) is None


def test_validation_requires_sentinel_nodes(monkeypatch):
    monkeypatch.setenv("UPLOAD_REDIS_MODE", "sentinel")
    from app.config.loader import load_settings
    from app.config.validation import validate_settings

    result = validate_settings(load_settings())
    assert not result.ok
    assert any("UPLOAD_SENTINEL_NODES" in error for error in result.errors)
