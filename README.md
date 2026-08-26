# PyUploadX 文件与目录上传服务

PyUploadX 是一个轻量、可独立部署、可水平扩展的文件与目录上传服务，提供统一的
文件上传、断点续传、目录上传、生命周期管理能力。详细设计与实现约束见
[产品设计说明书](docs/docs_product-design.md)（§31 目录结构、§16 REST API、§17 SDK）。

## 功能特性

- **上传模式**：小文件 Proxy 上传、大文件 Multipart（分片 + 预签名）、Local/S3/MinIO 存储适配
- **断点续传**：SDK 与 Portal 均支持指纹校验、状态恢复、缺失分片重传、URL 刷新
- **目录上传**：Manifest + NDJSON、路径安全校验、`.uploadignore`、冲突策略、双层并发
- **生命周期**：`permanent` / `ttl` / `expires_at` / `temporary` / `sliding_ttl`，Legal Hold、Webhook
- **集群一致性**：无状态 API 节点、PostgreSQL 行锁、Part Upsert、Complete/Abort 幂等
- **可观测性**：结构化 JSON 日志、Prometheus 指标、`/healthz` `/readyz` `/startupz`

## 技术栈

FastAPI · SQLAlchemy 2（ORM）· Alembic · PostgreSQL · Redis · boto3 · Python SDK（httpx）·
React + TypeScript + Vite + Dexie · Docker Compose · Kubernetes · pytest

## 快速开始（Docker Compose 单节点）

```bash
docker compose up -d --build
```

启动后：

- API/OpenAPI：http://localhost:8000/docs
- Portal：http://localhost:5173（API Key：`dev-key`）
- MinIO Console：http://localhost:9001（`minioadmin` / `minioadmin`）

也可按设计文档使用独立 Compose 文件：

```bash
docker compose -f deploy/single-node/compose.yaml up -d --build
docker compose -f deploy/cluster/compose.yaml up -d --build --scale api=3 --scale worker=2
```

## 本地开发

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,docs]"
python -m pytest tests -q          # 全量测试
ruff check app sdk upload_service tests scripts
uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

测试默认使用 SQLite（aiosqlite）；CI 使用 PostgreSQL。集群模式禁止 SQLite（`config validate` 会拒绝）。

## 配置

配置优先级：代码默认值 < `config/config.yaml` < 环境变量（`UPLOAD_SECTION__FIELD`）< 命令行。

```bash
python -m upload_service config validate
python -m upload_service config show --redact-secrets
python -m upload_service reconcile upload {upload_id} --dry-run
```

关键环境变量：

| 变量 | 说明 |
|---|---|
| `UPLOAD_API_KEYS` | JSON：`{"tenant/principal": ["key"]}` 或 key 数组 |
| `UPLOAD_DATABASE_URL` | SQLAlchemy 异步 URL |
| `UPLOAD_REDIS_URL` | Redis URL（`UPLOAD_REDIS__ENABLED=false` 可关闭） |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | S3/MinIO 凭据 |

## Python SDK

```python
from datetime import timedelta
from pyuploadx import UploadClient, FileLifecycle

client = UploadClient(
    base_url="http://localhost:8000",
    api_key="dev-key",
    state_dir="~/.pyuploadx/uploads",
)

# 小文件
result = client.upload_file(
    "./README.md",
    bucket="app-default",
    lifecycle=FileLifecycle.ttl(timedelta(days=30)),
)

# 大文件（Multipart + 断点续传）
result = client.upload_large_file(
    "./model.bin",
    bucket="app-default",
    object_key="models/model.bin",
    part_size=8 * 1024 * 1024,
    concurrency=4,
    resume=True,
)

# 目录上传
job = client.upload_directory(
    "./album-assets",
    bucket="app-default",
    destination_prefix="artists/10001/albums/2026",
    file_concurrency=8,
    part_concurrency=4,
    exclude=[".git/**", "**/*.tmp"],
    conflict_policy="reject",
)
```

## REST API 摘要

```text
GET  /healthz | /readyz | /startupz | /metrics
POST /v1/files/upload          GET/DELETE /v1/files/{id}
GET  /v1/files/{id}/download   POST /v1/files/{id}/presign-download
POST /v1/uploads               POST /v1/uploads/resume
GET  /v1/uploads/{id}          GET /v1/uploads/{id}/parts
POST /v1/uploads/{id}/parts/presign
PUT  /v1/uploads/{id}/parts/{part_number}
POST /v1/uploads/{id}/parts/commit
POST /v1/uploads/{id}/refresh | /complete | /abort
POST /v1/directory-uploads ... /v1/files/{id}/lifecycle ... /v1/client-config
```

错误响应统一为 `{"error": {"code", "message", "details", "retryable", "request_id"}}`。

## 项目结构

```text
app/        FastAPI 后端（api/config/core/db/storage/services/lifecycle/worker）
sdk/pyuploadx/  Python 客户端 SDK
portal/     React + TypeScript Portal（Dexie/IndexedDB 断点状态）
deploy/     单节点/集群 Compose、Kubernetes、Nginx、MinIO 引导
config/     YAML 配置示例
tests/      单元与集成测试
docs/       设计文档与架构图（SVG 源 / PNG 生成）
```

## 数据库与 ORM 契约

- 所有数据访问必须使用 SQLAlchemy 2 ORM（`app/db/models.py` + `app/db/repositories/`）。
- 禁止裸 SQL 字符串 DML；唯一例外是仓储层内基于
  `sqlalchemy.dialects.postgresql.insert` 的 `ON CONFLICT` Upsert。
- Schema 变更通过 Alembic 迁移交付。

## 文档图形（§35）

```bash
make diagrams          # 渲染 docs/assets/svg -> docs/assets/png
make diagrams-force    # 强制重新渲染
make docs-check        # 校验 PNG 未过期 + Markdown 引用 + SVG 安全（CI 门禁）
```

## 许可证

MIT
