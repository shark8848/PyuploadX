# PyUploadX 离线镜像部署手册

适用于：**无法直接访问外网拉取镜像**的目标服务器，在本机 `docker save` → 手工传输（U 盘 / scp / rsync）→ 目标机 `docker load` → `docker compose up -d --no-build`。

## 1. 镜像清单（单节点模式）

| 镜像:标签 | 大小 | 来源 | 用途 |
| --- | --- | --- | --- |
| `pyuploadx-upload-api:latest` | ~358 MB | `Dockerfile` target `api` | 上传/文件/目录 API |
| `pyuploadx-worker:latest` | ~358 MB | `Dockerfile` target `worker` | 生命周期/清理后台任务 |
| `pyuploadx-portal:latest` | ~110 MB | `portal/Dockerfile` | Portal 前端（OpenResty） |
| `pyuploadx-gateway:latest` | ~110 MB | `deploy/nginx/Dockerfile` | 生产网关（OpenResty，TLS 终止 + 反代；可选） |
| `pyuploadx-migrate:latest` | ~358 MB | `Dockerfile` target `api` | 一次性迁移（与 upload-api 同构建，仅入口为 `alembic upgrade head`） |
| `postgres:16-alpine` | ~420 MB | Docker Hub | 自带 PostgreSQL |
| `redis:7-alpine` | ~58 MB | Docker Hub | 自带 Redis |
| `minio/minio:latest` | ~241 MB | Docker Hub | 自带对象存储（compose 模式；数据外部卷挂载） |
| `minio/mc:latest` | ~117 MB | Docker Hub | 建桶初始化 |

合计约 **2.1 GB**（含压缩后更小）。`pyuploadx-migrate` 与 `pyuploadx-upload-api` 是同一构建产物，传输其一即可用 `docker tag` 补齐，但建议按清单全传，保证 `up -d` 直接命中。

> **数据一律外部挂载，不进镜像**：镜像只包含程序，不包含任何业务数据。
> - PostgreSQL / MinIO 数据存放在 compose 命名卷（`pyuploadx_postgres-data` /
>   `pyuploadx_minio-data`），删除或重建容器不丢数据；备份/恢复直接针对卷或宿主目录操作。
> - 独立运行加固 MinIO 镜像（`pyuploadx/minio-haproxy:latest`）时必须显式挂载外部数据目录：
>   `docker run -v /data/minio:/data ...`，镜像内不存在数据（见第 11 节）。

## 2. 本机导出

### 2.0 一键构建全部镜像（可选）

项目镜像（`pyuploadx-upload-api` / `pyuploadx-worker` / `pyuploadx-portal` /
`pyuploadx-gateway` / `pyuploadx-migrate` / 加固 MinIO `pyuploadx/minio-haproxy`）可一键构建：

```bash
bash scripts/build-images.sh            # 构建全部项目镜像（api/worker/portal/gateway/migrate/minio-haproxy）
bash scripts/build-images.sh --export   # 构建并 docker save 导出到 docker/images/
```

> **镜像名前缀**：缺省 `pyuploadx-`（本仓库口径）。ikc-demo 全栈要求 `ikc-*`，此时加前缀即可
> （非破坏性，缺省不变）：
> ```bash
> IMAGE_PREFIX=ikc-pyuploadx- bash scripts/build-images.sh --export
> # 镜像 ikc-pyuploadx-{upload-api,migrate,worker,portal,gateway}:latest
> # 包   docker/images/ikc-pyuploadx-*_latest.tar（ikc-demo 的 scripts/load-images.sh 可直接导入）
> ```
> 加固 MinIO `pyuploadx/minio-haproxy` 不受前缀影响（ikc 栈用上游 `minio/minio` → `ikc-minio`/`ikc-minio-mc`）。

> 第三方基础镜像（`postgres:16-alpine`、`redis:7-alpine`、`minio/mc:latest`）不随脚本构建，
> 离线发布时需另行 `docker pull` 后按下方命令 `docker save`。

### 2.1 单文件打包（推荐，最省事）

```bash
cd /home/sharkyai/PyUploadX
mkdir -p dist/offline
docker save -o dist/offline/pyuploadx-offline.tar \
  pyuploadx-upload-api:latest pyuploadx-worker:latest pyuploadx-portal:latest pyuploadx-migrate:latest \
  pyuploadx-gateway:latest \
  postgres:16-alpine redis:7-alpine minio/minio:latest minio/mc:latest
```

> `pyuploadx-gateway:latest` 为可选的生产 HTTPS 网关（OpenResty，见 §12）；不需要
> HTTPS 网关时可从导出列表移除，不影响 compose 模式启动。

### 2.2 逐个导出（便于分批/断点传输）

```bash
cd /home/sharkyai/PyUploadX
mkdir -p dist/offline
for img in \
  pyuploadx-upload-api:latest pyuploadx-worker:latest pyuploadx-portal:latest pyuploadx-migrate:latest \
  pyuploadx-gateway:latest \
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
  deploy/nginx/ \
  README.md
```

> `deploy/nginx/` 含生产网关的 `Dockerfile` 与 `gateway.conf`（配置来源，供参考或自建）；
> 离线目标机按镜像部署（`docker load`）即可，无需构建。

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
# Portal 自动登录 token（OpenResty 注入 X-API-Key；必须同时出现在 UPLOAD_API_KEYS 中）
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
- 生产网关（可选，见 §12）：`https://<域名>/`（TLS 终止 + HTTP→HTTPS 跳转）

防火墙需放行：`5173`、`8000`、`9000`、`9001`（PostgreSQL `5432`、Redis `6379` 仅本机/内网需要）。
部署生产网关后放行 `80`、`443` 即可，`5173`/`8000` 建议收回内网（避免绕过网关直连）。

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
| `80` / `443` | 生产网关（可选） | TLS 终止 + HTTP→HTTPS，见 §12 |
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

> **PG / Redis 不在宿主机、而在局域网其它主机时**：仅需把 `.env` 中
> `UPLOAD_DATABASE_URL` 的 `host.docker.internal:5432` 与 `UPLOAD_REDIS_URL` 的
> `host.docker.internal:6379` 换成对方主机 IP，例如
> `postgresql+asyncpg://upload:pass@192.168.1.20:5432/uploads`、
> `redis://:pass@192.168.1.21:6379/0`；其余配置不变（MinIO 仍在宿主机时，S3 端点保持
> `http://host.docker.internal:19000`，`--add-host` 参数保留即可）。
> 前提：PG/Redis 监听局域网地址（PG `listen_addresses` 含该网段、`pg_hba.conf` 放行应用宿主 IP；
> Redis `bind` 含该网段或 `0.0.0.0` 并设 `requirepass`），且对方防火墙允许应用宿主访问。

> **portal 容器不读取 `.env`**：`--env-file .env` 只对 API/Worker/Migrate 生效；portal 的
> token 必须用第 6 步的 `-e PORTAL_API_TOKEN=<实际值>` 显式传入。该值必须同时出现在
> `UPLOAD_API_KEYS` 中（如 `["dev-key","<实际值>"]`），否则 portal 注入的 `X-API-Key`
> 与 API 侧校验列表不匹配，登录报验证错误。

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

> `--network-alias upload-api` 必须有：portal 的 OpenResty 固定请求 `http://upload-api:8000`。

#### 6) Portal

```bash
# 示例 token：1qaz2wsx3edc（换成你自己的，必须与 .env 中 UPLOAD_API_KEYS 里的值一致）
docker run -d --name pyuploadx-portal --restart unless-stopped \
  --network pyuploadx-net --network-alias portal \
  -e PORTAL_API_TOKEN=1qaz2wsx3edc \
  -p 5173:80 \
  pyuploadx-portal:latest
```

> 不要照抄示例 token：换成与 `.env` 中 `UPLOAD_API_KEYS` 一致的值，且 `PORTAL_API_TOKEN`
> 必须用 `-e` 显式传入（portal 容器不读 `.env`）。若浏览器登录页曾手动输入过其它 key
> （localStorage 键名 `portal-token`），客户端 key 会覆盖 OpenResty 注入值，清除后重试。
> `--network-alias portal` 供生产网关（§12）反代解析；不部署网关时也可省略。

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

# 单独更新 portal（如修复后新镜像）：load → 删旧容器 → 重新 run
docker load -i pyuploadx-portal_latest.tar
docker rm -f pyuploadx-portal
docker run -d --name pyuploadx-portal --restart unless-stopped \
  --network pyuploadx-net --network-alias portal \
  -e PORTAL_API_TOKEN=1qaz2wsx3edc \
  -p 5173:80 \
  pyuploadx-portal:latest
# 确认新前端生效：docker exec pyuploadx-portal sh -c 'ls /usr/share/nginx/html/assets/ | grep index'

# 清理（不影响数据）
docker rm -f pyuploadx-upload-api pyuploadx-worker pyuploadx-portal
docker network rm pyuploadx-net
```

- 数据均在外部（PG/Redis/MinIO 卷或宿主目录），删除容器不丢数据；
  MinIO 备份见第 9 节。
- 登录点「登录」报「API Key 无效」且 portal/API 日志无 `/v1/files` 请求：多为浏览器
  仍加载旧前端包。旧版本 JS 在明文 HTTP（局域网 IP）下调用 `crypto.randomUUID()`（仅
  HTTPS/localhost 可用）会在发请求前抛错；更新到含回退逻辑的新 portal 镜像后
  强制刷新（Ctrl+Shift+R）即可。

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

## 12. 生产网关（可选，OpenResty HTTPS）

`pyuploadx-gateway:latest`（`deploy/nginx/Dockerfile`，OpenResty 1.31）对外只暴露
`80`/`443`：TLS 终止、HTTP→HTTPS 跳转，并把请求反代到 `portal:80`（页面）与
`upload-api:8000`（`/v1/`、`/healthz`）。网关内置安全加固（见 §13），无需手工配置；
配置来源为 `deploy/nginx/gateway.conf`，调整 `server_name` / 证书路径后需重新构建镜像。

### 12.1 准备证书

```bash
mkdir -p /etc/pyuploadx/certs
# 放置 TLS 证书与私钥（certbot / 自签均可），文件名固定为 tls.crt / tls.key
scp tls.crt tls.key root@SERVER:/etc/pyuploadx/certs/
```

> 网关镜像固定读取 `/etc/nginx/certs/tls.crt` 与 `tls.key`（对应
> `gateway.conf` 中的 `ssl_certificate` 路径）；改名需改配置后重建镜像。

### 12.2 compose 模式部署（第 6 节启动之后）

```bash
cd /opt/pyuploadx
docker run -d --name pyuploadx-gateway --restart unless-stopped \
  --network pyuploadx_default \
  -v /etc/pyuploadx/certs:/etc/nginx/certs:ro \
  -p 80:80 -p 443:443 \
  pyuploadx-gateway:latest
```

> 默认网络名为 `pyuploadx_default`（`deploy/single-node/compose.yaml` 声明
> `name: pyuploadx`）；同网络内 `portal`、`upload-api` 是 compose 服务名，网关可直接解析。

### 12.3 独立模式部署（第 8 节之后）

手动 `docker run` 的 `portal` 需带 `--network-alias portal`（见 §8.3 第 6 步），再启动网关：

```bash
docker run -d --name pyuploadx-gateway --restart unless-stopped \
  --network pyuploadx-net \
  -v /etc/pyuploadx/certs:/etc/nginx/certs:ro \
  -p 80:80 -p 443:443 \
  pyuploadx-gateway:latest
```

### 12.4 验证与日常运维

```bash
curl -sI http://localhost/                                   # 301 → https://$host/（Location 不带端口）
curl -skI https://localhost/                                 # TLS 正常；Server: openresty（无版本号）
curl -sk -o /dev/null -w '%{http_code}\n' \
  -H "X-API-Key: <实际 key>" https://localhost/v1/files?limit=1   # 200 = 网关→API 链路通

# 升级 / 重启：docker load 新镜像后重建（证书目录 -v 挂载不受影响）
docker rm -f pyuploadx-gateway
# 重新执行 12.2 / 12.3 的 docker run
```

- 域名解析到本机后，浏览器访问 `https://<域名>/` 即 Portal（自动登录）；
  网关 `server_name` 为 `upload.example.com`，可忽略（nginx 默认 server 兜底）或用实际域名重建镜像。
- 放行防火墙 `80`/`443`；`5173`/`8000` 建议收回内网。
- 客户端上传大文件：网关超时为空闲超时（见 §13），不影响长时间/断点续传。

## 13. 安全加固（内置，部署即生效）

Portal 与生产网关镜像已内置以下加固，无需手工配置：

- **隐藏版本与监听端口**：`server_tokens off` / `port_in_redirect off` /
  `absolute_redirect off`——`Server` 头不暴露版本号，重定向与错误响应不泄露内部端口。
- **安全响应头**：`X-Content-Type-Options: nosniff`（防 MIME 嗅探）、
  `X-Frame-Options: SAMEORIGIN`（防点击劫持）、
  `Referrer-Policy: strict-origin-when-cross-origin`（限制 Referrer 泄露）。
- **大文件兼容超时**：`proxy_connect_timeout 75s`，`proxy_read_timeout` /
  `proxy_send_timeout` / `client_body_timeout` 均 300s——均为空闲超时而非总时长，
  大文件持续传输不断连，慢速 / 暂停上传在 300s 内恢复不中断。
- **隐藏文件防护**（portal）：拒绝 `/.` 开头路径段（`.env` / `.git` 等），返回 403。

验证命令：

```bash
curl -sI http://<服务器IP>:5173/ | grep -iE '^(server|x-content-type|x-frame|referrer-policy)'
# 期望：Server: openresty（无版本号）+ 三个安全头
curl -s -o /dev/null -w '%{http_code}\n' http://<服务器IP>:5173/.env   # 期望 403
curl -sI http://localhost/ 2>/dev/null | grep -i location               # 网关 301，Location 无端口
```
