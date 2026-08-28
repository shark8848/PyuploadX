# PyUploadX Python SDK

`pyuploadx` 是 PyUploadX 文件/目录上传服务的 Python 客户端 SDK，支持小文件 Proxy 上传、
大文件 Multipart 分片 + 断点续传、目录上传（Manifest + `.uploadignore`）与生命周期策略。
协议与状态机见 `docs/docs_product-design.md` §17/§12/§13；**完整开发文档（方法参考/模型/异常/测试/发版）见 [docs/docs_sdk-dev.md](../../docs/docs_sdk-dev.md)**。

## 安装

```bash
pip install pyuploadx          # Python ≥ 3.11，第三方依赖仅 httpx
```

## 快速开始

```python
from datetime import timedelta
from pyuploadx import UploadClient, FileLifecycle

client = UploadClient(
    base_url="http://localhost:8000",
    api_key="dev-key",
    state_dir="~/.pyuploadx/uploads",
)

result = client.upload_file(
    "./README.md",
    bucket="app-default",
    lifecycle=FileLifecycle.ttl(timedelta(days=30)),
)

job = client.upload_directory(
    "./album-assets",
    bucket="app-default",
    destination_prefix="artists/10001",
    conflict_policy="reject",
)
```


## 获取结果与状态

上传接口同步返回结果对象（`FileInfo` / `DirectoryJobInfo`），后续可通过查询接口随时获取服务端最新状态。

```python
# 上传结果：文件元数据与状态（含临时预签名下载 URL，expires_in 秒；Local 后端为 None）
info = client.upload_file("./README.md", bucket="app-default")
print(info.id, info.status, info.size_bytes, info.etag)
print(info.download_url, info.expires_in)
url = client.get_download_url(info.id, expires_seconds=3600)    # 过期后重新获取

# 大文件 Multipart 会话：查询分片上传状态（status: initiated/uploading/completed）
session = client.create_upload(bucket="app-default", object_key="model.bin", total_size=1024, part_size=256)
probe = client.get_upload(session.id)
print(probe.status, probe.completed_file_id)

# 目录上传：任务统计与状态（completed/failed_files/uploaded_bytes）
job = client.upload_directory("./album-assets", bucket="app-default")
print(job.status, job.uploaded_files, job.failed_files, job.uploaded_bytes)

# 事后查询：文件最新状态、生命周期与下载
info = client.get_file(info.id)                 # FileInfo：status/expires_at/legal_hold/completed_at
lifecycle = client.get_lifecycle(info.id)       # 生效生命周期
client.update_lifecycle(info.id, {"mode": "ttl", "ttl_seconds": 3600})
client.download(
    info.id,
    "/tmp/README.md",
    progress=lambda done, total: print(f"{done}/{total}"),
)  # 代理流式下载
client.download(info.id, "/tmp/README.md", url=url)  # 直接用预签名/永久链接 URL 下载
client.download_from_url(url, "/tmp/README.md")      # 等价，无需 file_id
client.delete(info.id)                          # 删除（幂等）
```

### 指定目录上传、返回 URL 与 URL 下载

```python
import httpx

# 1) 指定目录上传：自动拼接 object_key = <directory>/<文件名>
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

# 3) 使用 URL 下载（httpx 流式写盘，不占内存）
with httpx.stream("GET", url, follow_redirects=True) as resp:
    resp.raise_for_status()
    with open("/tmp/report.pdf", "wb") as f:
        for chunk in resp.iter_bytes():
            f.write(chunk)
```

## 永久下载链接（服务端能力）

永久链接的**创建**未封装为 SDK 方法（保持服务端 API 直调）；消费侧由 v0.6.0 新增的
`download_from_url()` 流式下载：

```python
import httpx
link = httpx.post(
    f"{base}/v1/files/{info.id}/permanent-link",
    headers={"X-API-Key": "dev-key"},
).json()["url"]                      # 永不过期（文件删除前有效）
client.download_from_url(link, "/tmp/report.pdf")   # 流式下载，支持 progress 回调
```

详见 `docs/docs_sdk-dev.md` §11。

## 发版

SDK 与服务端分开发布：SDK 包 `pyuploadx` 在本目录构建
（`bash scripts/publish-pypi.sh`），服务端包 `pyuploadx-server` 在仓库根构建
（`bash scripts/publish-pypi-server.sh`），详见 `docs/docs_product-design.md` §37。
