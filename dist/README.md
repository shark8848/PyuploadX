# 发布产物（保留历史版本）

`dist/` 保存每次发版构建的 wheel 与 sdist，**所有历史版本均保留**，并打对应版本标签。

## pyuploadx（Python SDK，构建于 `sdk/pyuploadx/`）

| 版本 | 标签 | wheel | 说明 |
| --- | --- | --- | --- |
| `0.1.0` | `v0.1.0` | `dist/pyuploadx-0.1.0-py3-none-any.whl` | 首个合并版（SDK + 服务端同包） |
| `0.2.0` | `v0.2.0` | `dist/pyuploadx-0.2.0-py3-none-any.whl` | 拆分后 SDK-only，第三方依赖仅 httpx |
| `0.3.0` | `v0.3.0` | `dist/pyuploadx-0.3.0-py3-none-any.whl` | 新增 `get_upload`/`get_directory_job` 状态查询；目录上传上报成功条目（统计真实） |
| `0.4.0` | `v0.4.0` | `dist/pyuploadx-0.4.0-py3-none-any.whl` | 上传/完成响应附带临时预签名 `download_url`/`expires_in`；新增 `get_download_url` |
| `0.5.0` | `v0.5.0` | `dist/pyuploadx-0.5.0-py3-none-any.whl` | 上传支持 `directory` 参数自动拼 object_key（示例：指定目录上传 + URL 下载） |
| `0.6.0` | `v0.6.0` | `dist/pyuploadx-0.6.0-py3-none-any.whl` | download URL 模式（`use_url` 自动选择/降级）与 `download_from_url` |
| `0.7.0` | `v0.7.0` | `dist/pyuploadx-0.7.0-py3-none-any.whl` | 简化 download：默认代理流式；`url=` 或 `download_from_url` 直接下载 URL（移除 `use_url`/`expires_seconds` 自动逻辑） |

## pyuploadx-server（服务端，构建于仓库根）

| 版本 | 标签 | wheel | 说明 |
| --- | --- | --- | --- |
| `0.1.0` | `server-v0.1.0` | `dist/pyuploadx_server-0.1.0-py3-none-any.whl` | 拆分后服务端独立包（app/ + upload_service/） |
| `0.1.1` | `server-v0.1.1` | `dist/pyuploadx_server-0.1.1-py3-none-any.whl` | 上传/完成响应附带临时预签名 `download_url`/`expires_in` |
| `0.1.2` | `server-v0.1.2` | `dist/pyuploadx_server-0.1.2-py3-none-any.whl` | 永久下载链接：`POST /v1/files/{id}/permanent-link` + 无鉴权 `download-link`（HMAC） |

## 安装

```bash
pip install pyuploadx                                # SDK（官方 PyPI，Python ≥ 3.11）
pip install pyuploadx-server                         # 服务端（官方 PyPI）
pip install dist/pyuploadx-0.2.0-py3-none-any.whl    # 仓库直装，可指定任意历史版本
```

## 发版约定

1. 更新版本号：SDK 在 `sdk/pyuploadx/pyproject.toml`（+ `sdk/pyuploadx/__init__.py`），
   服务端在根 `pyproject.toml`。
2. `bash scripts/publish-pypi.sh` 发布 SDK；`bash scripts/publish-pypi-server.sh` 发布服务端。
3. 提交 `dist/` 产物，打标签（SDK `vX.Y.Z`，服务端 `server-vX.Y.Z`），
   推送分支与标签到 `origin` 与 `tiancloud`。
