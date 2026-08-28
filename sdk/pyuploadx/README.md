# PyUploadX Python SDK

`pyuploadx` 是 PyUploadX 文件/目录上传服务的 Python 客户端 SDK，支持小文件 Proxy 上传、
大文件 Multipart 分片 + 断点续传、目录上传（Manifest + `.uploadignore`）与生命周期策略。
协议与状态机见 `docs/docs_product-design.md` §17/§12/§13。

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

## 发版

SDK 与服务端分开发布：SDK 包 `pyuploadx` 在本目录构建
（`bash scripts/publish-pypi.sh`），服务端包 `pyuploadx-server` 在仓库根构建
（`bash scripts/publish-pypi-server.sh`），详见 `docs/docs_product-design.md` §37。
