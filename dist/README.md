# 发布产物（保留历史版本）

`dist/` 保存每次发版构建的 wheel 与 sdist，**所有历史版本均保留**，并打对应版本标签（`v0.1.0`、`v0.2.0` …）。

## 已发布版本

| 版本 | 标签 | wheel | 说明 |
| --- | --- | --- | --- |
| `0.1.0` | `v0.1.0` | `dist/pyuploadx-0.1.0-py3-none-any.whl` | 首版：Python SDK（上传/断点续传/目录/生命周期）+ 服务端 |

## 安装

```bash
pip install pyuploadx                              # 官方 PyPI
pip install dist/pyuploadx-0.1.0-py3-none-any.whl  # 仓库直装，可指定任意历史版本
```

## 发版约定

1. 更新版本号（`pyproject.toml` + `sdk/pyuploadx/__init__.py`）。
2. `bash scripts/publish-pypi.sh`：构建 wheel/sdist 到 `dist/`（保留历史）并上传 PyPI。
3. 提交 `dist/` 产物，打标签 `vX.Y.Z`，推送分支与标签到 `origin` 与 `tiancloud`。
