# PyUploadX SDK 开发文档

`pyuploadx` 是 PyUploadX 文件/目录上传服务的 Python 客户端 SDK：小文件 Proxy 上传、
大文件 Multipart 分片 + 断点续传、目录上传（Manifest + `.uploadignore`）、生命周期管理、
预签名下载。协议与状态机以 `docs/docs_product-design.md`（§12/§13/§16/§17）为准。

## 1. 安装

```bash
pip install pyuploadx          # 官方 PyPI（Python ≥ 3.11，第三方依赖仅 httpx）
pip install dist/pyuploadx-0.4.0-py3-none-any.whl   # 或仓库直装（见 dist/README.md）
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
| `upload_file(path, *, bucket, object_key=None, lifecycle=None, metadata=None)` | `FileInfo` | 小文件 Proxy 上传 |
| `upload_large_file(path, *, bucket, object_key=None, part_size=8MiB, concurrency=4, resume=True, lifecycle=None)` | `FileInfo` | 大文件 Multipart + 断点续传 |
| `create_upload(*, bucket, object_key, total_size, part_size, file_fingerprint=None, expected_sha256=None, lifecycle=None)` | `UploadSessionInfo` | 手动创建分片会话 |
| `upload_directory(path, *, bucket, destination_prefix="", recursive=True, resume=True, file_concurrency=8, part_concurrency=4, include=None, exclude=None, symlink_policy="ignore", conflict_policy="reject", lifecycle=None)` | `DirectoryJobInfo` | 目录上传 |
| `get_file(file_id)` | `FileInfo` | 文件最新状态 |
| `get_upload(upload_id)` | `UploadSessionInfo` | 分片会话最新状态 |
| `get_directory_job(job_id)` | `DirectoryJobInfo` | 目录任务最新状态与统计 |
| `get_download_url(file_id, expires_seconds=None)` | `str \| None` | 预签名下载 URL（Local 后端为 `None`） |
| `download(file_id, destination)` | `Path` | 下载到本地（Local 后端亦可用） |
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

# 分片会话 / 目录任务状态
session = client.get_upload(upload_id)                 # status, completed_file_id
job = client.get_directory_job(job_id)                 # uploaded_files / failed_files

# 生命周期查询与变更
lifecycle = client.get_lifecycle(info.id)
client.update_lifecycle(info.id, {"mode": "ttl", "ttl_seconds": 3600})

# 下载与删除
client.download(info.id, "/tmp/README.md")
client.delete(info.id)
```

- `download_url` 有有效期（`expires_in`，默认 900 秒，上限 86400），完整 URL 不会写入服务端日志。
- Local 存储不支持预签名（`presigned_get=False`）：上传响应 `download_url=None`、
  `get_download_url()` 返回 `None`，此时请使用 `download()` 走服务端代理下载。

## 6. 目录上传

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

## 7. 断点续传与本地状态

- 状态保存在 `state_dir`（默认 `~/.pyuploadx/uploads`）：
  - `uploads/{upload_id}.json` — 大文件分片进度；
  - `directories/{directory_upload_id}.sqlite3` — 目录条目进度。
- `upload_large_file(resume=True)`：按文件指纹（sha256）校验本地进度，仅重传缺失分片，
  完成后清理本地状态。
- 页面/进程重启后本地状态丢失时，重新上传即可；服务端会话可通过
  `POST /v1/uploads/{id}/resume` 续传（SDK 自动处理）。

## 8. 异常与错误码

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

## 9. 开发与测试

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "sdk/pyuploadx[dev]"      # SDK + dev extras（pytest）
# 或仓库根：pip install -e ".[dev]"

python -m pytest tests/integration/test_sdk.py -q     # SDK 集成测试（内存 ASGI，无需起服务）
python -m pytest tests/unit tests/integration -q      # 全量（S3 套件需 UPLOAD_MINIO_TEST=1）
```

- `tests/conftest.py` 自动把 `sdk/` 加入 `sys.path`，SDK 源码可直接被测试导入。
- 新增 SDK 方法请在 `tests/integration/test_sdk.py` 补充断言（Local 后端路径）。

## 10. 发版

SDK 与服务端为两个独立发布包（`pyuploadx` / `pyuploadx-server`），流程见
`docs/docs_product-design.md` §37：

1. 更新版本号：`sdk/pyuploadx/pyproject.toml` + `sdk/pyuploadx/__init__.py`。
2. `bash scripts/publish-pypi.sh` 构建并上传 SDK；`bash scripts/publish-pypi-server.sh` 上传服务端。
3. 提交 `dist/` 产物，打标签（SDK `vX.Y.Z`，服务端 `server-vX.Y.Z`），推送 `origin` 与 `tiancloud`。
