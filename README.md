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

## 快速开始（Docker Compose）

PostgreSQL / Redis / MinIO 等第三方组件**不随应用镜像构建**：默认通过环境变量指向
本地或已有实例（默认地址 `host.docker.internal`，即宿主机；端口与凭据均可覆盖）。

方式 A：使用本地/已有 PostgreSQL、Redis、MinIO

```bash
# 可选：覆盖默认地址与凭据
export UPLOAD_DATABASE_URL='postgresql+asyncpg://upload:upload@localhost:5432/uploads'
export UPLOAD_REDIS_URL='redis://localhost:6379/0'
export UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL='http://localhost:9000'
export S3_ACCESS_KEY=minioadmin S3_SECRET_KEY=minioadmin
docker compose up -d --build          # migrate → upload-api → worker → portal
```

方式 B：自带第三方组件（`deploy/infra/compose.yaml`，端口可用 `POSTGRES_PORT`、
`REDIS_PORT`、`MINIO_PORT` 覆盖）

```bash
docker compose -f deploy/infra/compose.yaml up -d          # postgres/redis/minio + 建桶
docker compose up -d --build                               # 应用服务
```

单节点/集群一键（含组件）：

```bash
docker compose -f deploy/single-node/compose.yaml up -d --build
docker compose -f deploy/cluster/compose.yaml up -d --build --scale upload-api=3 --scale worker=2
```

启动后：

- API/OpenAPI：http://localhost:8000/docs
- Portal：http://localhost:5173（API Key：`dev-key`）
- MinIO Console：http://localhost:9001（`minioadmin` / `minioadmin`）

## Kubernetes 部署

模板位于 `deploy/kubernetes/`（Namespace / Deployment / Service / Ingress / HPA / PDB /
Secret / ConfigMap / ServiceMonitor）。API 默认 3 副本、`maxUnavailable: 0`、优雅终止 60s，
并通过 `/readyz` 探针摘除故障节点。ServiceMonitor（`servicemonitor.yaml`）可被
Prometheus Operator 直接发现：

```bash
kubectl apply -f deploy/kubernetes/
```

生产强制 HTTPS：Ingress 终止 TLS；单节点/集群部署由 `deploy/nginx/gateway.conf` 强制跳转
HTTPS 并拒绝非白名单 Origin 的 CORS 请求。

## 本地开发

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,docs]"
python -m pytest tests -q          # 全量测试
ruff check app sdk upload_service tests scripts
uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

测试默认使用 SQLite（aiosqlite）；CI 使用 PostgreSQL。集群模式禁止 SQLite（`config validate` 会拒绝）。

### 数据库迁移（Alembic）

```bash
alembic upgrade head    # 升级到最新 schema
alembic downgrade -1    # 回退一个版本（仅限向后兼容的迁移）
make migrate            # 等价于 alembic upgrade head
```

Schema 变更一律通过 Alembic 迁移交付，禁止用临时脚本改表（见 AGENTS.md Architecture Contracts）。

### MinIO / S3 Adapter 测试

```bash
UPLOAD_MINIO_TEST=1 \
UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL=http://localhost:9000 \
S3_ACCESS_KEY=minioadmin S3_SECRET_KEY=minioadmin \
python -m pytest tests/integration/test_s3_storage.py -q
```

未设置 `UPLOAD_MINIO_TEST=1` 时该套件自动跳过；CI 内置 MinIO 服务并始终运行它。

### Portal E2E（Playwright）

```bash
cd portal
npm ci
npx playwright install chromium      # 首次运行需下载浏览器
npx playwright test                   # 自动拉起 uvicorn(8000) 与 vite(5173)
```

E2E 覆盖登录与错误展示、文件/目录上传、生命周期策略、刷新后队列恢复（§29.6）。
本地默认 `E2E_API_URL=http://127.0.0.1:8000`、`E2E_PORTAL_URL=http://127.0.0.1:5173`，
API Key 为 `e2e-key`（由 `portal/playwright.config.ts` 注入，SQLite + local 存储）。
CI 的 portal job 会安装浏览器依赖并执行同一套测试。

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

## 备份与恢复

运维手册见 [`docs/operations.md`](docs/operations.md)：PostgreSQL 每日全量备份与 PITR、
对象存储 Versioning/复制/对象锁、恢复顺序（先 DB → 对象存储 → Redis → API 只读检查 →
Reconcile Dry Run → Worker → 开放入口）、向后兼容的迁移与回滚原则（§28）。

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

## 可观测性

- 健康检查：`/healthz`（Liveness）、`/readyz`（Readiness，检测数据库连通性）、`/startupz`。
- 指标：`/metrics`（Prometheus 文本格式），覆盖上传/分片/断点/目录/生命周期/数据库/Redis/
  Storage 全链路；Kubernetes 下由 `deploy/kubernetes/servicemonitor.yaml` 抓取。
- 日志：结构化 JSON（request_id / trace_id / node_id / tenant_id / duration_ms 等），
  不记录 Secret、完整 API Key 或完整预签名 URL（§23）。

## 性能测试

```bash
python scripts/benchmark_upload.py --base-url http://localhost:8000 \
    --api-key dev-key --files 100 --concurrency 16
python scripts/benchmark_upload.py --large-mb 64 --part-size 8388608 --concurrency 8
```

场景对应 §29.7：并发小文件 Proxy 上传与 1 GiB 级大文件 Multipart（走 SDK 断点续传链路），
输出吞吐与 p50/p95 延迟。大规模场景（10 万小文件、目录总大小 1 TiB）请在目标环境按需调参。

## 项目结构

```text
app/        FastAPI 后端（api/config/core/db/storage/services/lifecycle/worker）
sdk/pyuploadx/  Python 客户端 SDK
portal/     React + TypeScript Portal（Dexie/IndexedDB 断点状态）
deploy/     单节点/集群 Compose、Kubernetes（含 ServiceMonitor）、Nginx、MinIO 引导
config/     YAML 配置示例
tests/      单元与集成测试
scripts/    渲染/文档检查/看板同步/性能测试脚本
docs/       设计文档、运维手册与架构图（SVG 源 / PNG 生成）
```

## 数据库与 ORM 契约

- 所有数据访问必须使用 SQLAlchemy 2 ORM（`app/db/models.py` + `app/db/repositories/`）。
- 禁止裸 SQL 字符串 DML；唯一例外是仓储层内基于
  `sqlalchemy.dialects.postgresql.insert` 的 `ON CONFLICT` Upsert。
- Schema 变更通过 Alembic 迁移交付。

## 安全要点

- 生产强制 HTTPS（Nginx/Ingress TLS 终止），CORS 仅允许显式配置的 Origin。
- Secret 只通过环境变量注入，禁止写入 YAML 或提交到仓库；日志脱敏密钥与完整签名 URL。
- PostgreSQL/Redis 不暴露公网（Compose 仅内部网络，K8s 无外部 Service）。
- 对象 Key 与目录相对路径均做防路径逃逸校验；上传会话校验所有权，Complete/Abort 幂等。

## 文档图形（§35）

```bash
make diagrams          # 渲染 docs/assets/svg -> docs/assets/png
make diagrams-force    # 强制重新渲染
make docs-check        # 校验 PNG 未过期 + Markdown 引用 + SVG 安全（CI 门禁）
```

## 许可证

MIT
