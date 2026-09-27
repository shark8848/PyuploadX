"""Redis 客户端装配：连接形态（单机 / 副本 / 哨兵）由公共工厂 `ikc_sdk.redis` 决定。

站点侧只给 `UPLOAD_*` 环境变量：

- ``single`` / ``replica``：`UPLOAD_REDIS_URL`（要连哨兵代理就是这一形态 + 代理地址）；
- ``sentinel``：`UPLOAD_SENTINEL_NODES`（``host:port,...``）+ `UPLOAD_SENTINEL_MASTER_NAME` /
  `UPLOAD_SENTINEL_PASSWORD` / `UPLOAD_SENTINEL_AUTH_PASSWORD` / `UPLOAD_SENTINEL_DB`。

与四个引擎的 Celery 面（`ikc_sdk.celery`）是同一套 ``<PREFIX>_*`` 口径（见 `ikc_sdk.redis`
模块 docstring 与 `ikc-sdk-lib/AGENTS.md` §12）；`config/config.yaml` 只声明开关与前缀，
不再承载连接串形状 —— 避免「YAML 一套、工厂一套」两处口径。
"""

from __future__ import annotations

import logging

from ikc_sdk.redis import RedisConfig, RedisFactory
from redis.asyncio import Redis

from app.config.models import Settings

logger = logging.getLogger("upload_service.redis")

#: 站点侧环境变量前缀（`UPLOAD_REDIS_URL` / `UPLOAD_SENTINEL_*`）。
ENV_PREFIX = "UPLOAD"


def connection_config() -> RedisConfig:
    """按 `UPLOAD_*` 解析连接形态（只读环境，不建连、不落库）。"""
    return RedisConfig.from_env(ENV_PREFIX)


def build_redis(settings: Settings) -> Redis | None:
    """构建 Redis 客户端。

    `redis.enabled=false`、或单机 / 副本形态没给 `UPLOAD_REDIS_URL` 时返回 None（只告警，
    不拦启动）——与旧行为一致：Redis 不保存不可恢复状态，缺它不影响本地上传链路。
    """
    if not settings.redis.enabled:
        return None
    config = connection_config()
    if config.mode in {"single", "replica"} and not config.url:
        logger.warning("%s_REDIS_URL is empty; redis client disabled", ENV_PREFIX)
        return None
    return RedisFactory.create(config, decode_responses=True)
