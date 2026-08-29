# PyUploadX SDK 开发文档

`pyuploadx` 是 PyUploadX 文件/目录上传服务的 Python 客户端 SDK：小文件 Proxy 上传、
大文件 Multipart 分片 + 断点续传、目录上传（Manifest + `.uploadignore`）、生命周期管理、
预签名下载。协议与状态机以 `docs/docs_product-design.md`（§12/§13/§16/§17）为准。

## 1. 安装

```bash
pip install pyuploadx          # 官方 PyPI（Python ≥ 3.11，第三方依赖仅 httpx）
pip install dist/pyuploadx-0.8.0-py3-none-any.whl   # 或仓库直装（历史版本清单见 dist/README.md）
```

## 2. 客户端初始化

```python
from pyuploadx import UploadClient

client = UploadClient(
    base_url="https://uploads.example.com",   # 必填；API 服务地址
    bearer_token="...",                        # 与 api_key 二选一
    # api_key="dev-key",
    state_dir="~/.pyuploadx/uploads",          # 断点续传本地状态目录（默认）
    timeout=60.0,                              # httpx 超时（秒）
)

with client as c:                              # 上下文管理器，自动 close
    info = c.upload_file("./README.md", bucket="app-default")

client.on_progress(lambda uploaded, total: print(f"{uploaded}/{total}"))  # 上传进度
```

- 认证：`bearer_token`（`Authorization: Bearer`）或 `api_key`（`X-API-Key`），必须二选一。
- `transport` 参数可注入自定义 `httpx.BaseTransport`（测试用内存 ASGI 传输）。
- 客户端是线程安全的会话封装；`close()` 释放连接池。

## 3. 方法参考

| 方法 | 返回 | 说明 |
| --- | --- | --- |
| `upload_file(path, *, bucket, object_key=None, directory=None, lifecycle=None, metadata=None)` | `FileInfo` | 小文件 Proxy 上传（`directory` 自动拼目录） |
| `upload_large_file(path, *, bucket, object_key=None, directory=None, part_size=8MiB, concurrency=4, resume=True, lifecycle=None)` | `FileInfo` | 大文件 Multipart + 断点续传（`directory` 自动拼目录） |
| `create_upload(*, bucket, object_key, total_size, part_size, file_fingerprint=None, expected_sha256=None, lifecycle=None)` | `UploadSessionInfo` | 手动创建分片会话 |
| `upload_directory(path, *, bucket, destination_prefix="", recursive=True, resume=True, file_concurrency=8, part_concurrency=4, include=None, exclude=None, symlink_policy="ignore", conflict_policy="reject", lifecycle=None)` | `DirectoryJobInfo` | 目录上传 |
| `get_file(file_id)` | `FileInfo` | 文件最新状态 |
| `list_files(*, bucket=None, prefix=None, status=None, limit=50, offset=0, sort_by="name")` | `dict` | 分页列出文件（§16.2，返回 `{"items": [...], "total": n}`） |
| `get_upload(upload_id)` | `UploadSessionInfo` | 分片会话最新状态 |
| `get_directory_job(job_id)` | `DirectoryJobInfo` | 目录任务最新状态与统计 |
| `get_download_url(file_id, expires_seconds=None)` | `str \| None` | 预签名下载 URL（Local 后端为 `None`） |
| `download(file_id, destination, *, url=None, progress=None, concurrency=1)` | `Path` | 下载到本地：默认代理流式下载；传入 `url=` 直接下载 URL；`concurrency>1` 并发 Range 分片（不支持时自动回退单流） |
| `download_from_url(url, destination, *, progress=None, concurrency=1)` | `Path` | 直接流式下载任意 HTTP(S) URL（预签名/永久链接），支持并发分片 |
| `delete(file_id)` | `None` | 删除（幂等） |
| `get_lifecycle(file_id)` | `dict` | 生效生命周期 |
| `update_lifecycle(file_id, lifecycle)` | `dict` | 更新生命周期 |
| `extend_lifecycle(file_id, extend_seconds)` | `dict` | 延长 TTL |
| `set_legal_hold(file_id, hold=True)` | `dict` | 设置/取消 Legal Hold |
| `on_progress(callback)` | `None` | 上传进度回调 |

## 4. 数据模型

- `FileInfo`：`id` / `bucket` / `object_key` / `original_filename` / `size_bytes` /
  `content_type` / `etag` / `checksum_value` / `status` / `lifecycle_mode` /
  `expires_at` / `legal_hold` / `completed_at` / `download_url` / `expires_in`。
- `UploadSessionInfo`：`id` / `bucket` / `object_key` / `total_size` / `part_size` /
  `total_parts` / `upload_mode` / `backend` / `status`（initiated/uploading/completed/…）/
  `completed_file_id` / `effective_lifecycle` / `expires_at`。
- `DirectoryJobInfo`：`id` / `status` / `total_entries` / `total_files` /
  `total_directories` / `total_bytes` / `uploaded_files` / `uploaded_bytes` /
  `failed_files` / `skipped_files` / `manifest_hash` / `effective_lifecycle`。
- `UploadedPart`：`part_number` / `etag` / `size_bytes` / `checksum_sha256`。

## 5. 结果与状态查询

上传接口**同步返回**结果对象；服务端状态可随时查询：

```python
# 上传响应自带临时预签名下载 URL（S3/MinIO；Local 后端为 None）
info = client.upload_file("./README.md", bucket="app-default")
print(info.id, info.status, info.size_bytes)
print(info.download_url, info.expires_in)              # 临时 URL 与有效秒数

# 过期后重新获取
url = client.get_download_url(info.id, expires_seconds=3600)

# 分页浏览文件（可按桶 / 前缀过滤，按名称或创建时间排序）
page = client.list_files(bucket="app-default", status="active", limit=50, sort_by="created_at")
print(page["total"], page["items"])

# 分片会话 / 目录任务状态
session = client.get_upload(upload_id)                 # status, completed_file_id
job = client.get_directory_job(job_id)                 # uploaded_files / failed_files

# 生命周期查询与变更
lifecycle = client.get_lifecycle(info.id)
client.update_lifecycle(info.id, {"mode": "ttl", "ttl_seconds": 3600})

# 下载与删除（默认代理流式下载；需要 URL 时显式传入）
client.download(info.id, "/tmp/README.md")          # 代理流式；progress(written, total) 可选
client.download(info.id, "/tmp/README.md", url=url)  # 直接使用预签名/永久链接 URL
client.download_from_url(url, "/tmp/README.md")     # 等价，无需 file_id
client.download(info.id, "/tmp/big.bin", concurrency=8)  # 超大文件：并发 Range 分片
client.delete(info.id)
```

- `download_url` 有有效期（`expires_in`，默认 900 秒，上限 86400），完整 URL 不会写入服务端日志。
- Local 存储不支持预签名（`presigned_get=False`）：上传响应 `download_url=None`、
  `get_download_url()` 返回 `None`，此时请使用 `download()` 走服务端代理下载。

## 6. 指定目录上传、返回 URL 与 URL 下载

```python
import httpx

# 1) 指定目录上传：object_key = <directory>/<文件名>（object_key 显式传入时优先）
info = client.upload_file(
    "./report.pdf",
    bucket="app-default",
    directory="reports/2026",          # => object_key: reports/2026/report.pdf
)
large = client.upload_large_file(
    "./model.bin",
    bucket="app-default",
    directory="models/backup",         # => object_key: models/backup/model.bin
)

# 2) 上传响应返回临时预签名下载 URL（expires_in 秒；Local 后端为 None）
print(info.download_url, info.expires_in)
url = client.get_download_url(info.id, expires_seconds=3600)   # 过期后重新获取

# 3) 使用 URL 下载：SDK 流式写盘，不占内存，支持 progress 回调
client.download_from_url(url, "/tmp/report.pdf",
                         progress=lambda done, total: print(f"{done}/{total}"))
# 或：client.download(info.id, "/tmp/report.pdf", url=url)  # 等价，需 file_id

# 等价实现：原始 httpx 流式写盘
with httpx.stream("GET", url, follow_redirects=True) as resp:
    resp.raise_for_status()
    with open("/tmp/report.pdf", "wb") as f:
        for chunk in resp.iter_bytes():
            f.write(chunk)
```

- `directory` 经 `normalize_relative_path` 归一化：去首尾 `/`、`\` 转 `/`、拒绝 `.`/`..`/绝对路径/盘符路径。
- `object_key` 与 `directory` 同时给出时以 `object_key` 为准。
- 下载三选一：`download(file_id, ...)`（代理流式）、`download(file_id, ..., url=...)` 或
  `download_from_url(url, ...)`（预签名/永久链接）、原始 `httpx.stream`（与 SDK 等价）。
- `download` / `download_from_url` 均逐块写盘，不整体缓冲；`progress(written, total)` 可选回调。
- 需要预签名 URL 时先调 `get_download_url(file_id, expires_seconds=...)`（或上传响应
  `download_url` / 永久链接 API），再交给 `url=` / `download_from_url` 下载，无需其它判断。

### 超大文件多线程下载（HTTP Range）

`download()` / `download_from_url()` 支持 `concurrency=N`（默认 1）并行分片下载：

```python
# 代理下载：服务端支持 Range（206）时并发分片，不支持时自动回退单流
client.download(info.id, "/tmp/big.bin", concurrency=8,
                progress=lambda done, total: print(f"{done}/{total}"))

# URL 下载（预签名/永久链接）同样支持并发
client.download_from_url(url, "/tmp/big.bin", concurrency=8)
```

- SDK 先发 `Range: bytes=0-0` 探测；服务端返回 206 才启用并发，否则自动单流下载。
- 每个线程下载一个字节区间并写入对应偏移（不整体缓冲）；进度按累计字节回调。
- 服务端 `GET /v1/files/{id}/download` 与 `download-link` 均支持 Range（206 + `Content-Range`，
  越界/非法返回 416 `RANGE_NOT_SATISFIABLE`）；S3/MinIO 预签名 URL 原生支持 Range。

## 7. 目录上传


```python
job = client.upload_directory(
    "./album-assets",
    bucket="app-default",
    destination_prefix="artists/10001/albums/2026",
    file_concurrency=8,
    part_concurrency=4,
    include=["**/*.jpg", "**/*.md"],
    exclude=[".git/**", "**/*.tmp", "**/.DS_Store"],
    symlink_policy="ignore",       # ignore | follow | reject
    conflict_policy="reject",      # reject | skip | overwrite
    lifecycle=FileLifecycle.ttl(timedelta(days=30)),
)
print(job.status, job.uploaded_files, job.failed_files, job.uploaded_bytes)
```

- `.uploadignore` 文件（gitignore 语法）在客户端本地过滤；`exclude` 优先级高于 `include`。
- SDK 逐条上报条目结果（uploaded/failed），服务端 `aggregate_progress` 聚合统计。
- 目录相对路径做防路径逃逸校验；Manifest 哈希由服务端核对。

## 8. 断点续传与本地状态

- 状态保存在 `state_dir`（默认 `~/.pyuploadx/uploads`）：
  - `uploads/{upload_id}.json` — 大文件分片进度；
  - `directories/{directory_upload_id}.sqlite3` — 目录条目进度。
- `upload_large_file(resume=True)`：按文件指纹（sha256）校验本地进度，仅重传缺失分片，
  完成后清理本地状态。
- 页面/进程重启后本地状态丢失时，重新上传即可；服务端会话可通过
  `POST /v1/uploads/{id}/resume` 续传（SDK 自动处理）。

## 9. 异常与错误码

所有异常继承 `pyuploadx.UploadClientError`，并带 `status_code` 属性。服务端错误码
（`{"error": {"code": ...}}`）与 SDK 异常的映射：

| 错误码 | SDK 异常 |
| --- | --- |
| `AUTHENTICATION_REQUIRED` / `FORBIDDEN` | `AuthenticationError` / `AuthorizationError` |
| `INVALID_BUCKET` / `OBJECT_ALREADY_EXISTS` 等 | `ValidationError` |
| `INVALID_LIFECYCLE_POLICY` / `TTL_OUT_OF_RANGE` | `LifecycleError` |
| `UPLOAD_NOT_FOUND` / `UPLOAD_ABORTED` / `UPLOAD_EXPIRED` | `ResumeError` |
| `MISSING_PARTS` / `PART_ETAG_MISMATCH` / `UPLOAD_STATE_CONFLICT` | `MultipartError` |
| `CHECKSUM_MISMATCH` | `ChecksumMismatchError` |
| `MANIFEST_HASH_MISMATCH` / `DIRECTORY_HAS_FAILED_ENTRIES` | `DirectoryUploadError` |
| `STORAGE_UNAVAILABLE` / `DATABASE_UNAVAILABLE` | `StorageUnavailableError` |
| 未知错误码 / 网络错误 | `UploadClientError` / `ServerError` |

网络抖动时客户端自动重试（408/429/5xx），并支持上传进度回调。

## 10. 开发与测试

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "sdk/pyuploadx[dev]"      # SDK + dev extras（pytest）
# 或仓库根：pip install -e ".[dev]"

python -m pytest tests/integration/test_sdk.py -q     # SDK 集成测试（内存 ASGI，无需起服务）
python -m pytest tests/unit tests/integration -q      # 全量（S3 套件需 UPLOAD_MINIO_TEST=1）
```

- `tests/conftest.py` 自动把 `sdk/` 加入 `sys.path`，SDK 源码可直接被测试导入。
- 新增 SDK 方法请在 `tests/integration/test_sdk.py` 补充断言（Local 后端路径）。

## 11. 永久下载链接（服务端能力）

永久链接的**创建**未封装为 SDK 方法（保持服务端 API 直调，未新增创建接口）；
消费侧由 v0.8.0 提供的 `download_from_url()` 与 `download(..., url=...)`（含 `concurrency` 并发分片）支持：

```bash
# 创建永久链接（需鉴权）→ 返回永不过期的下载 URL
curl -X POST http://localhost:8000/v1/files/<file_id>/permanent-link \
  -H "X-API-Key: dev-key"

# 结果：{"url": ".../v1/files/<file_id>/download-link?token=<hmac>", "permanent": true}
```

```python
import httpx

base = "http://localhost:8000"
headers = {"X-API-Key": "dev-key"}
resp = httpx.post(f"{base}/v1/files/{info.id}/permanent-link", headers=headers)
link = resp.json()["url"]                     # 永久链接（文件删除前一直有效）

# 或直接用 SDK 的 URL 下载模式（流式写盘，支持 progress 回调）
client.download_from_url(link, "/tmp/report.pdf")
```

- 链接永不过期；文件删除后返回 404，token 错误返回 403。
- 签名密钥：环境变量 `UPLOAD_PERMANENT_LINK_SECRET`（未配置时创建链接返回 501）。
- 吊销：轮换 `UPLOAD_PERMANENT_LINK_SECRET` 后所有旧链接立即失效。

## 12. 发版


SDK 与服务端为两个独立发布包（`pyuploadx` / `pyuploadx-server`），流程见
`docs/docs_product-design.md` §37：

1. 更新版本号：`sdk/pyuploadx/pyproject.toml` + `sdk/pyuploadx/__init__.py`。
2. `bash scripts/publish-pypi.sh` 构建并上传 SDK；`bash scripts/publish-pypi-server.sh` 上传服务端。
3. 提交 `dist/` 产物，打标签（SDK `vX.Y.Z`，服务端 `server-vX.Y.Z`），推送 `origin` 与 `tiancloud`。
