# PyUploadX 离线镜像部署手册

适用于：**无法直接访问外网拉取镜像**的目标服务器，在本机 `docker save` → 手工传输（U 盘 / scp / rsync）→ 目标机 `docker load` → `docker compose up -d --no-build`。

## 1. 镜像清单（单节点模式）

| 镜像:标签 | 大小 | 来源 | 用途 |
| --- | --- | --- | --- |
| `pyuploadx-upload-api:latest` | ~358 MB | `Dockerfile` target `api` | 上传/文件/目录 API |
| `pyuploadx-worker:latest` | ~358 MB | `Dockerfile` target `worker` | 生命周期/清理后台任务 |
| `pyuploadx-portal:latest` | ~75 MB | `portal/Dockerfile` | Portal 前端（nginx） |
| `pyuploadx-migrate:latest` | ~358 MB | `Dockerfile` target `api` | 一次性迁移（与 upload-api 同构建，仅入口为 `alembic upgrade head`） |
| `postgres:16-alpine` | ~420 MB | Docker Hub | 自带 PostgreSQL |
| `redis:7-alpine` | ~58 MB | Docker Hub | 自带 Redis |
| `minio/minio:latest` | ~241 MB | Docker Hub | 自带对象存储（compose 模式；数据外部卷挂载） |
| `minio/mc:latest` | ~117 MB | Docker Hub | 建桶初始化 |

合计约 **1.9 GB**（含压缩后更小）。`pyuploadx-migrate` 与 `pyuploadx-upload-api` 是同一构建产物，传输其一即可用 `docker tag` 补齐，但建议按清单全传，保证 `up -d` 直接命中。

> **数据一律外部挂载，不进镜像**：镜像只包含程序，不包含任何业务数据。
> - PostgreSQL / MinIO 数据存放在 compose 命名卷（`pyuploadx_postgres-data` /
>   `pyuploadx_minio-data`），删除或重建容器不丢数据；备份/恢复直接针对卷或宿主目录操作。
> - 独立运行加固 MinIO 镜像（`pyuploadx/minio-haproxy:latest`）时必须显式挂载外部数据目录：
>   `docker run -v /data/minio:/data ...`，镜像内不存在数据（见第 11 节）。

## 2. 本机导出

### 2.0 一键构建全部镜像（可选）

项目镜像（`pyuploadx-upload-api` / `pyuploadx-worker` / `pyuploadx-portal` /
`pyuploadx-migrate` / 加固 MinIO `pyuploadx/minio-haproxy`）可一键构建：

```bash
bash scripts/build-images.sh            # 构建全部项目镜像（api/worker/portal/minio-haproxy）
bash scripts/build-images.sh --export   # 构建并 docker save 导出到 docker/images/
```

> 第三方基础镜像（`postgres:16-alpine`、`redis:7-alpine`、`minio/mc:latest`）不随脚本构建，
> 离线发布时需另行 `docker pull` 后按下方命令 `docker save`。

### 2.1 单文件打包（推荐，最省事）

```bash
cd /home/sharkyai/PyUploadX
mkdir -p dist/offline
docker save -o dist/offline/pyuploadx-offline.tar \
  pyuploadx-upload-api:latest pyuploadx-worker:latest pyuploadx-portal:latest pyuploadx-migrate:latest \
  postgres:16-alpine redis:7-alpine minio/minio:latest minio/mc:latest
```

### 2.2 逐个导出（便于分批/断点传输）

```bash
cd /home/sharkyai/PyUploadX
mkdir -p dist/offline
for img in \
  pyuploadx-upload-api:latest pyuploadx-worker:latest pyuploadx-portal:latest pyuploadx-migrate:latest \
  postgres:16-alpine redis:7-alpine minio/minio:latest minio/mc:latest; do
  name=$(echo "$img" | tr '/:' '__')
  docker save -o "dist/offline/${name}.tar" "$img"
done
```

### 2.3 部署配置打包（镜像之外还需要 compose 文件）

```bash
cd /home/sharkyai/PyUploadX
tar czf dist/offline/pyuploadx-compose.tgz \
  docker-compose.yml \
  deploy/single-node/compose.yaml \
  deploy/infra/compose.yaml \
  README.md
```

## 3. 传输到目标服务器

```bash
# 示例（scp），或使用 rsync / U 盘
scp dist/offline/pyuploadx-offline.tar root@SERVER:/opt/pyuploadx-offline/
scp dist/offline/pyuploadx-compose.tgz root@SERVER:/opt/pyuploadx-offline/
```

## 4. 目标服务器导入

```bash
mkdir -p /opt/pyuploadx && cd /opt/pyuploadx
tar xzf /opt/pyuploadx-offline/pyuploadx-compose.tgz

# 导入镜像（单文件）
docker load -i /opt/pyuploadx-offline/pyuploadx-offline.tar
# 或逐个导入
# for f in /opt/pyuploadx-offline/*.tar; do docker load -i "$f"; done

# 校验：与第 1 节清单一致
docker images | grep -E 'pyuploadx|postgres|redis|minio'
docker compose -f deploy/single-node/compose.yaml config --images
```

## 5. 配置 `.env`

在 `/opt/pyuploadx/.env` 创建（`docker compose` 会从当前目录自动读取）：

```bash
cd /opt/pyuploadx
# 先生成 token（也可手动指定固定值）
TOKEN=$(openssl rand -hex 16)
cat > .env <<'EOF'
# Portal 自动登录 token（nginx 注入 X-API-Key；必须同时出现在 UPLOAD_API_KEYS 中）
PORTAL_API_TOKEN=REPLACE_WITH_TOKEN
# 后端校验的 API Key（含 portal token；可追加其它 key，如 "dev-key"）
UPLOAD_API_KEYS=["dev-key","REPLACE_WITH_TOKEN"]
# 自带组件：容器网络直连（推荐，不依赖宿主端口映射）
UPLOAD_DATABASE_URL=postgresql+asyncpg://upload:upload@postgres:5432/uploads
UPLOAD_REDIS__ENABLED=true
UPLOAD_REDIS_URL=redis://redis:6379/0
UPLOAD_CLUSTER__ENABLED=false
UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL=http://minio:9000
UPLOAD_STORAGE__S3__PUBLIC_ENDPOINT_URL=http://<服务器IP>:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
# 可选：IKC Log Center 日志投递（默认关闭）
UPLOAD_LOG_CENTER__ENABLED=false
UPLOAD_LOG_CENTER__URL=http://<log-center IP>:9315
LOG_CENTER_TOKEN=
EOF
sed -i "s/REPLACE_WITH_TOKEN/$TOKEN/g" .env
```

> 注意：`PORTAL_API_TOKEN` 必须同时出现在 `UPLOAD_API_KEYS` 中（`sed` 会同步替换两处），否则 Portal 自动登录会 401。
> 若服务器已有外部 PostgreSQL/Redis/MinIO，可省略自带组件模式，改用「独立模式」（见第 8 节）。

## 6. 启动（离线环境禁止 `--build`）

```bash
cd /opt/pyuploadx
docker compose -f deploy/single-node/compose.yaml up -d --no-build
```

启动顺序由 compose 自动编排：`migrate`（alembic 迁移，成功即退出）→ `upload-api` / `worker` → `portal`；`minio-bootstrap` 首次自动创建 `app-default` / `public-assets` 桶。

就绪检查：

```bash
docker compose -f deploy/single-node/compose.yaml ps
curl -fsS http://localhost:8000/healthz && echo OK
curl -fsS http://localhost:9001/minio/health/live && echo OK
# migrate 应显示 Exited (0)，属正常（一次性 Job）
```

## 7. 访问入口

- Portal：`http://<服务器IP>:5173`（自动登录）
- API / OpenAPI：`http://<服务器IP>:8000/docs`
- MinIO Console：`http://<服务器IP>:9001`（`minioadmin` / `minioadmin`）

防火墙需放行：`5173`、`8000`、`9000`、`9001`（PostgreSQL `5432`、Redis `6379` 仅本机/内网需要）。

## 8. 独立模式（复用已有 PG/Redis/MinIO）

只部署 4 个应用镜像（`pyuploadx-upload-api` / `pyuploadx-worker` / `pyuploadx-portal` /
`pyuploadx-migrate`），数据库 / Redis / 对象存储全部使用已有实例，不启动自带组件。

### 8.1 前置条件与端口

- 4 个应用镜像已在目标机 `docker load`（见 §4）；MinIO（S3 API 端口 / 控制台端口）与
  PostgreSQL、Redis 已就绪。
- 应用容器通过 `host.docker.internal` 访问宿主机服务（`--add-host host.docker.internal:host-gateway`）；
  若 PG/Redis/MinIO 不在本机，将 `.env` 中的地址替换为实际可达地址。
- 端口清单（冲突检查：`ss -ltnp | grep -E ':(8060|5173|19000|19001)\b'`）：

| 端口 | 用途 | 说明 |
| --- | --- | --- |
| `8060` | API | 容器 8000 → 宿主 8060（`-p 8060:8000`，可改） |
| `5173` | Portal | 容器 80 → 宿主 5173（`-p 5173:80`，可改） |
| `19000` | MinIO S3 API | 应用存储端点（HAProxy 前置） |
| `19001` | MinIO Console | 管理控制台 |
| `5432` / `6379` | PostgreSQL / Redis | 通常仅内网/本机可达 |

### 8.2 方式 A：有 compose 插件

```bash
cd /opt/pyuploadx
export UPLOAD_DATABASE_URL='postgresql+asyncpg://user:pass@host.docker.internal:5432/dbname'
export UPLOAD_REDIS_URL='redis://:password@host.docker.internal:6379/0'
export UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL='http://host.docker.internal:19000'
export UPLOAD_STORAGE__S3__PUBLIC_ENDPOINT_URL='http://<服务器IP>:19000'
export S3_ACCESS_KEY=minioadmin S3_SECRET_KEY=...
export PORTAL_API_TOKEN='...' UPLOAD_API_KEYS='["dev-key","..."]'
docker compose -f docker-compose.yml up -d --no-build
```

> 镜像必须已 `docker load`，否则 `--no-build` 会尝试从 registry 拉取并失败（本地镜像未推送）。

### 8.3 方式 B：无 compose，手动 docker run（离线环境推荐）

#### 1) 建网络（一次）

```bash
docker network create pyuploadx-net   # 只影响显式加入该网络的容器，不影响其它服务
```

#### 2) 环境变量文件 `.env`（`docker run --env-file` 不解析 `${}`，填具体值）

```bash
cat > .env <<'EOF'
UPLOAD_API_KEYS=["dev-key","REPLACE_PORTAL_TOKEN"]
UPLOAD_DATABASE_URL=postgresql+asyncpg://<用户>:<密码>@host.docker.internal:5432/<库名>
UPLOAD_REDIS__ENABLED=true
UPLOAD_REDIS_URL=redis://:<密码>@host.docker.internal:6379/0
UPLOAD_CLUSTER__ENABLED=false
UPLOAD_LOG_CENTER__ENABLED=false
UPLOAD_LOG_CENTER__URL=http://host.docker.internal:9315
LOG_CENTER_TOKEN=
UPLOAD_STORAGE__S3__INTERNAL_ENDPOINT_URL=http://host.docker.internal:19000
UPLOAD_STORAGE__S3__PUBLIC_ENDPOINT_URL=http://<服务器IP>:19000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=<MinIO 密码>
EOF
```

> `REPLACE_PORTAL_TOKEN` 必须与 portal 容器的 `PORTAL_API_TOKEN` 一致：portal 的 nginx 会把它作为
> `X-API-Key` 注入 `/v1/` 请求，API 侧通过 `UPLOAD_API_KEYS` 校验。

#### 3) MinIO 建桶引导（全新实例才需要）

```bash
docker run --rm --add-host host.docker.internal:host-gateway \
  --entrypoint /bin/sh minio/mc:latest -c '
  mc alias set local http://host.docker.internal:19000 minioadmin <MinIO 密码> >/dev/null &&
  mc mb --ignore-existing local/app-default &&
  mc mb --ignore-existing local/public-assets &&
  mc anonymous set download local/public-assets >/dev/null &&
  mc ls local'
```

#### 4) 数据库迁移（等待成功退出 0）

```bash
docker run --rm --name pyuploadx-migrate \
  --network pyuploadx-net \
  --add-host host.docker.internal:host-gateway \
  --env-file .env \
  pyuploadx-migrate:latest alembic upgrade head
```

#### 5) API 与 Worker

```bash
docker run -d --name pyuploadx-upload-api --restart unless-stopped \
  --network pyuploadx-net --network-alias upload-api \
  --add-host host.docker.internal:host-gateway \
  --env-file .env \
  -p 8060:8000 \
  pyuploadx-upload-api:latest

docker run -d --name pyuploadx-worker --restart unless-stopped \
  --network pyuploadx-net \
  --add-host host.docker.internal:host-gateway \
  --env-file .env \
  pyuploadx-worker:latest
```

> `--network-alias upload-api` 必须有：portal 的 nginx 固定请求 `http://upload-api:8000`。

#### 6) Portal

```bash
docker run -d --name pyuploadx-portal --restart unless-stopped \
  --network pyuploadx-net \
  -e PORTAL_API_TOKEN=REPLACE_PORTAL_TOKEN \
  -p 5173:80 \
  pyuploadx-portal:latest
```

#### 7) 验证与访问

```bash
docker ps --format '{{.Names}}\t{{.Status}}'
curl -fsS http://localhost:8060/healthz && echo OK
curl -fsS -o /dev/null -w 'portal:%{http_code}\n' http://localhost:5173/
```

- API / OpenAPI：`http://<服务器IP>:8060/docs`
- Portal：`http://<服务器IP>:5173`（自动登录）
- MinIO Console：`http://<服务器IP>:19001`

#### 8) 运维

```bash
# 停止 / 启动 / 重启
docker stop pyuploadx-upload-api pyuploadx-worker pyuploadx-portal
docker start pyuploadx-upload-api pyuploadx-worker pyuploadx-portal
docker restart pyuploadx-upload-api pyuploadx-worker pyuploadx-portal

# 升级：docker load 新镜像后依次重建（migrate 会自动执行增量迁移）
docker rm -f pyuploadx-upload-api pyuploadx-worker pyuploadx-portal
# 先跑迁移（等待退出码 0，命令同第 4 步）
docker run --rm --name pyuploadx-migrate \
  --network pyuploadx-net \
  --add-host host.docker.internal:host-gateway \
  --env-file .env \
  pyuploadx-migrate:latest alembic upgrade head
# 再按第 5、6 步重新 run

# 清理（不影响数据）
docker rm -f pyuploadx-upload-api pyuploadx-worker pyuploadx-portal
docker network rm pyuploadx-net
```

- 数据均在外部（PG/Redis/MinIO 卷或宿主目录），删除容器不丢数据；
  MinIO 备份见第 9 节。

## 9. 常用运维

- 查看日志：`docker compose -f deploy/single-node/compose.yaml logs -f upload-api`
- 停止：`docker compose -f deploy/single-node/compose.yaml down`（数据卷保留；`down -v` 会删除数据，慎用）
- 升级：重新 `docker save`/传输/`docker load` 新镜像 → `docker compose up -d --no-build`（`migrate` 自动执行增量迁移）
- 数据备份：
  - PostgreSQL：`docker exec pyuploadx-postgres-1 pg_dump -U upload uploads > backup.sql`
  - MinIO：`docker run --rm -v pyuploadx_minio-data:/data -v $(pwd):/backup alpine tar czf /backup/minio-data.tgz -C /data .`
  - MinIO（独立加固镜像、宿主目录挂载）：`docker run --rm -v /data/minio:/data -v $(pwd):/backup alpine tar czf /backup/minio-data.tgz -C /data .`

## 10. 集群模式（可选）

集群使用独立项目名与镜像前缀，镜像为 `pyuploadx-cluster-upload-api` / `pyuploadx-cluster-worker` / `pyuploadx-cluster-portal` / `pyuploadx-cluster-migrate`（与单节点同构建产物，仅 compose 项目名不同），第三方组件同上：

```bash
docker save -o dist/offline/pyuploadx-cluster.tar \
  pyuploadx-cluster-upload-api:latest pyuploadx-cluster-worker:latest \
  pyuploadx-cluster-portal:latest pyuploadx-cluster-migrate:latest \
  postgres:16-alpine redis:7-alpine minio/minio:latest minio/mc:latest
# 目标机导入后
cd /opt/pyuploadx
docker compose -f deploy/cluster/compose.yaml up -d --no-build --scale upload-api=3 --scale worker=2
```

集群约束：必须使用 PostgreSQL（禁 SQLite）；多副本共享同一数据库与对象存储；Local 后端需共享文件系统（建议 S3/MinIO）。

## 11. 加固 MinIO 镜像（独立部署）

`pyuploadx/minio-haproxy:latest` 为加固镜像：MinIO 只监听容器内回环地址
（S3 `127.0.0.1:19000` / 控制台 `127.0.0.1:19001`），外部仅通过容器内 HAProxy
暴露 `9000`（S3 API）与 `9001`（控制台），屏蔽 MinIO 服务端直连面。

本机构建（脚本基于本地缓存的基础镜像离线构建，无需访问外网）：

```bash
bash deploy/minio/build.sh                          # 构建 pyuploadx/minio-haproxy:latest

# 可选参数：
MINIO_IMAGE_TAG=registry.example.com/pyuploadx/minio-haproxy:latest bash deploy/minio/build.sh
MINIO_BASE_IMAGE=minio/minio:RELEASE.2025-09-07T16-13-09Z bash deploy/minio/build.sh   # 指定 MinIO 基础版本
```

本机导出：

```bash
docker save -o docker/images/pyuploadx__minio-haproxy_latest.tar \
  pyuploadx/minio-haproxy:latest
```

目标机加载并运行（**数据必须外部挂载**，镜像内无数据）：

```bash
docker load -i docker/images/pyuploadx__minio-haproxy_latest.tar

# 宿主目录挂载（推荐，便于备份）：-v /data/minio:/data
docker run -d --name pyuploadx-minio --restart unless-stopped \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  -v /data/minio:/data \
  -p 9000:9000 -p 9001:9001 \
  pyuploadx/minio-haproxy:latest /data

# 或命名卷挂载：-v minio-data:/data（同样不进镜像）
```

- `/data` 为 MinIO 数据目录，必须由宿主目录或命名卷提供；容器重建 / 升级后数据保留。
- 首次部署建桶（`app-default` / `public-assets`）用 `minio/mc` 执行 `deploy/minio/bootstrap.sh`。
- 备份/恢复直接针对挂载的宿主目录或卷（见第 9 节）。
