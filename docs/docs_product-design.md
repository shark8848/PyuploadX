# PyUploadX 文件与目录上传服务产品设计说明书

> 文档版本：v1.4 Consolidated  
> 更新日期：2026-08-26  
> 文档类型：产品需求说明书 + 技术架构设计 + 部署设计  
> 目标读者：Codex、后端工程师、SDK 工程师、前端工程师、测试工程师、DevOps/SRE  
> 核心技术：FastAPI、Python SDK、React Portal、PostgreSQL、Redis、Local/S3/MinIO、Docker Compose、Kubernetes

---

## 目录

1. [产品概述](#1-产品概述)
2. [设计原则](#2-设计原则)
3. [范围定义](#3-范围定义)
4. [用户角色与使用场景](#4-用户角色与使用场景)
5. [功能需求](#5-功能需求)
6. [非功能需求](#6-非功能需求)
7. [总体架构](#7-总体架构)
8. [技术栈](#8-技术栈)
9. [领域模型与术语](#9-领域模型与术语)
10. [数据模型](#10-数据模型)
11. [文件上传流程](#11-文件上传流程)
12. [断点续传](#12-断点续传)
13. [目录上传](#13-目录上传)
14. [文件生命周期](#14-文件生命周期)
15. [Storage Adapter](#15-storage-adapter)
16. [REST API](#16-rest-api)
17. [Python Client SDK](#17-python-client-sdk)
18. [Portal](#18-portal)
19. [YAML 配置](#19-yaml-配置)
20. [集群与一致性](#20-集群与一致性)
21. [后台任务](#21-后台任务)
22. [安全设计](#22-安全设计)
23. [可观测性](#23-可观测性)
24. [单节点部署](#24-单节点部署)
25. [集群部署](#25-集群部署)
26. [Kubernetes 部署](#26-kubernetes-部署)
27. [生产组网](#27-生产组网)
28. [备份、恢复、升级和回滚](#28-备份恢复升级和回滚)
29. [测试方案](#29-测试方案)
30. [性能与容量规划](#30-性能与容量规划)
31. [项目目录](#31-项目目录)
32. [实施计划](#32-实施计划)
33. [Codex 开发任务](#33-codex-开发任务)
34. [Definition of Done](#34-definition-of-done)
35. [架构图生成规范](#35-架构图生成规范)
36. [最终技术决策](#36-最终技术决策)

---

# 1. 产品概述

## 1.1 产品名称

建议：

```text
服务名称：upload-service
Python SDK：pyuploadx
Portal：upload-portal
```

## 1.2 产品定位

建设一个轻量、可独立部署、可水平扩展的文件上传服务，统一提供：

- FastAPI REST 服务；
- Python Client SDK；
- Web Portal；
- Local、S3、MinIO 存储适配；
- 小文件代理上传；
- 大文件分片上传；
- 预签名 URL 直传；
- 文件和目录断点续传；
- 目录递归上传；
- 文件生命周期管理；
- 单节点和集群部署；
- Docker Compose 一键运行；
- Kubernetes 生产部署。

## 1.3 核心目标

1. 开发环境可以通过 `docker compose up` 启动。
2. SDK 可以通过简单接口上传文件和目录。
3. Portal 可以通过 HTTP/HTTPS 页面上传文件和目录。
4. 上传中断后只重新上传缺失文件或分片。
5. API 节点无状态，可水平扩展。
6. 文件生命周期可以由 SDK、Portal 或 API 声明。
7. Local、S3 和 MinIO 通过统一 Adapter 接口访问。
8. 大文件优先使用预签名 URL 直传，降低 API 节点带宽压力。
9. 所有关键操作支持幂等、审计、监控和故障恢复。

---

# 2. 设计原则

1. **API 节点无状态**：上传会话不得只保存在应用进程内。
2. **PostgreSQL 是权威状态源**：文件、上传、目录、生命周期和幂等状态统一持久化。
3. **Redis 不保存不可恢复状态**：仅用于限流、缓存、进度和短期租约。
4. **存储后端可插拔**：业务层不得依赖具体 S3、MinIO 或本地实现。
5. **大文件直传优先**：支持预签名 URL 时，客户端直接上传对象存储。
6. **服务端不信任客户端**：路径、大小、分片、ETag、生命周期和权限必须重新校验。
7. **上传和生命周期分离**：上传状态与文件生命周期状态使用不同状态机。
8. **SDK 本地状态不是权威源**：恢复时必须与服务端及存储端对账。
9. **不依赖粘性会话**：上传流程中的不同请求可以进入不同 API 节点。
10. **所有完成和删除操作幂等**：重复调用不能产生重复文件或错误状态。
11. **配置与密钥分离**：普通配置使用 YAML，Secret 使用环境变量或 Secret Manager。
12. **SVG 为图形源文件**：通过构建脚本生成 PNG，Markdown 只引用 PNG。

---

# 3. 范围定义

## 3.1 本期范围

### 服务端

- FastAPI REST API；
- API Key 和 Bearer Token 鉴权；
- 文件上传、下载、查询、删除；
- 小文件代理上传；
- 分片上传；
- 预签名 PUT、GET 和 UploadPart URL；
- 断点续传；
- 目录上传；
- 文件生命周期；
- Local、S3、MinIO；
- PostgreSQL；
- Redis；
- Worker；
- 健康检查；
- Prometheus 指标；
- 结构化日志。

### Python SDK

- 同步客户端；
- 文件上传；
- 大文件分片上传；
- 目录递归上传；
- 自动重试；
- 断点续传；
- 生命周期声明和修改；
- 上传进度回调；
- 本地状态持久化。

### Portal

- 文件选择；
- 目录选择；
- 拖放上传；
- 多文件队列；
- Proxy 和 Presigned 上传；
- 暂停、继续、取消；
- 页面刷新后恢复；
- 生命周期选择；
- 上传状态和错误展示。

### 部署

- 单节点 Docker Compose；
- 多 API、多 Worker Compose 集群；
- Kubernetes 部署模板；
- Nginx/Gateway；
- MinIO 初始化；
- SVG 到 PNG 文档构建。

## 3.2 暂不实现

- 完整的企业级 RBAC 管理后台；
- 在线病毒扫描；
- 内容审核；
- CDN 自动刷新；
- 文件在线编辑；
- 实时同步本地目录；
- 将目录同步语义扩展为双向同步；
- tus 协议服务端；
- 超大目录同步打包下载；
- 跨地域多活。

这些能力需要在当前架构上预留扩展点。

---

# 4. 用户角色与使用场景

## 4.1 角色

| 角色 | 说明 |
|---|---|
| SDK 用户 | Python 应用、脚本、数据处理任务 |
| Portal 用户 | 通过浏览器上传文件和目录 |
| 业务系统 | 使用 REST API 管理上传任务和文件 |
| 管理员 | 配置 Bucket、策略、生命周期和权限 |
| Worker | 执行清理、删除、归档、对账和 Webhook |
| 运维人员 | 部署、监控、备份和故障恢复 |

## 4.2 典型场景

### 小文件上传

```text
SDK/Portal
→ FastAPI
→ StorageAdapter.put_object
→ 创建 file_objects
→ 返回 file_id
```

### 大文件上传

```text
客户端创建上传会话
→ 获取分片预签名 URL
→ 并发上传分片到 S3/MinIO
→ 上报 ETag
→ Complete
→ 创建 file_objects
```

### 目录上传

```text
扫描目录
→ 生成 Manifest
→ 创建目录任务
→ 分批提交 Manifest
→ 为文件创建上传会话
→ 上传缺失文件和分片
→ 完成目录任务
```

### 临时文件

```text
上传时声明 TTL
→ 文件完成后开始计时
→ Lifecycle Worker 到期删除
```

---

# 5. 功能需求

## 5.1 文件能力

- 上传；
- 下载；
- 删除；
- 查询元数据；
- 查询存储状态；
- 预签名下载；
- 文件生命周期查询和修改；
- Legal Hold；
- 文件完整性校验；
- Metadata。

## 5.2 上传模式

| 模式 | 数据路径 | 适用场景 |
|---|---|---|
| Proxy | 客户端 → FastAPI → 存储 | Local、小文件、内网 |
| Presigned | 客户端 → 对象存储 | 大文件、Portal、公网 |
| Automatic | SDK/Portal 自动选择 | 默认模式 |

默认建议：

```text
小于 20 MiB：Proxy
大于等于 20 MiB：Presigned Multipart
```

最终模式由服务端根据存储能力和安全策略决定。

## 5.3 断点续传

必须支持：

- 网络中断恢复；
- SDK 进程退出恢复；
- Portal 页面刷新恢复；
- API 节点退出恢复；
- 预签名 URL 过期后重新签发；
- 缺失分片查询；
- 文件级和目录级恢复；
- Complete 响应丢失后安全重试；
- 只重新上传缺失内容。

## 5.4 目录上传

必须支持：

- 递归扫描；
- 保留相对目录结构；
- `.uploadignore`；
- Include/Exclude；
- 路径安全校验；
- Manifest；
- 大 Manifest 分批提交；
- NDJSON 流式提交；
- 双层并发；
- 目录级生命周期；
- 文件级生命周期覆盖；
- 空目录可选保留；
- 冲突策略；
- 目录级暂停、恢复和取消。

## 5.5 生命周期

支持：

```text
permanent
ttl
expires_at
temporary
sliding_ttl
```

支持动作：

```text
delete
notify
none
```

扩展动作：

```text
archive
transition
restore
```

---

# 6. 非功能需求

## 6.1 可用性

- API 支持多个副本；
- 单个 API 节点退出不丢失上传状态；
- Worker 支持多个副本；
- 上传会话可跨节点恢复；
- Readiness 自动摘除故障节点。

## 6.2 性能

建议初始目标：

| 指标 | 目标 |
|---|---:|
| 非上传 API P95 | 200 ms 内 |
| Presign API P95 | 300 ms 内 |
| 状态查询 P95 | 200 ms 内 |
| 默认分片大小 | 8 MiB |
| SDK 默认文件并发 | 8 |
| SDK 默认分片并发 | 4 |
| 默认总 HTTP 并发上限 | 16 |
| 默认预签名有效期 | 15 分钟 |

对象存储网络耗时不计入 API 内部处理延迟。

## 6.3 可靠性

- Complete 幂等；
- Abort 幂等；
- 生命周期删除幂等；
- Manifest Batch 幂等；
- SDK 状态原子写入；
- Local 文件原子 Rename；
- Worker 任务可重试；
- 数据库和存储端支持对账。

## 6.4 安全

- 防路径穿越；
- MIME 和大小限制；
- Bucket 白名单；
- 上传会话所有权；
- 生命周期权限；
- CORS 白名单；
- HTTPS；
- Secret 脱敏；
- 预签名 URL 短时有效；
- 管理端点不公开。

---

# 7. 总体架构

![系统总体架构](assets/png/system-architecture.png)

## 7.1 组件

```text
客户端层：
- Python SDK
- Upload Portal
- 业务应用
- Web/Mobile Client

接入层：
- Nginx
- Load Balancer
- WAF
- Kubernetes Ingress

应用层：
- FastAPI API
- Lifecycle Worker
- Cleanup Worker
- Reconcile Worker
- Webhook Worker

状态层：
- PostgreSQL
- Redis

存储层：
- Local Disk
- NFS/CephFS/RWX PVC
- MinIO
- AWS S3或兼容对象存储

可观测层：
- Prometheus
- Grafana
- OpenTelemetry
- Loki/OpenSearch
```

## 7.2 数据流

### 控制流

```text
Client
→ Gateway
→ FastAPI
→ PostgreSQL/Redis
→ Storage Adapter
```

### 大文件数据流

```text
Client
→ FastAPI：创建会话和获取签名
→ S3/MinIO：直接上传数据
→ FastAPI：提交分片和完成
```

---

# 8. 技术栈

| 层次 | 首选 | 说明 |
|---|---|---|
| Web API | FastAPI | REST、OpenAPI、异步服务 |
| ASGI Server | Uvicorn | 开发和基础运行 |
| 进程管理 | Gunicorn/Uvicorn Worker 或容器多副本 | 按部署模式选择 |
| Schema | Pydantic v2 | 请求、响应和配置校验 |
| ORM | SQLAlchemy 2 | Async ORM |
| Migration | Alembic | 数据库迁移 |
| Database | PostgreSQL | 权威状态 |
| Cache | Redis | 限流、缓存、进度 |
| S3 SDK | boto3/aiobotocore | S3 和 MinIO |
| Local IO | pathlib、aiofiles | Local 存储 |
| Python SDK | httpx | HTTP 客户端 |
| Portal | React + TypeScript + Vite | 浏览器上传 |
| Portal 状态 | IndexedDB + Dexie | 断点状态 |
| Testing | pytest、pytest-asyncio、Playwright | 服务、SDK、Portal |
| Metrics | prometheus-client | Prometheus |
| Tracing | OpenTelemetry | 分布式追踪 |
| Container | Docker | 镜像构建 |
| Dev Deployment | Docker Compose | 一键启动 |
| Production | Kubernetes | 集群部署 |
| Diagram | SVG + CairoSVG | 生成 PNG |

---

# 9. 领域模型与术语

## 9.1 File Object

已完成上传且可被查询、下载或管理生命周期的文件。

## 9.2 Upload Session

一个文件的上传会话，负责：

- 存储上传 ID；
- 分片大小；
- 分片数量；
- 已上传分片；
- 上传状态；
- 超时；
- 最终文件关联。

## 9.3 Directory Upload Job

目录上传聚合任务，包含多个目录清单项和文件上传会话。

## 9.4 Manifest

描述目录中所有文件、路径、大小、类型和指纹的清单。

## 9.5 Storage Adapter

屏蔽 Local、S3 和 MinIO 差异的存储抽象接口。

## 9.6 Presigned URL

由服务端签发的短期 URL，允许客户端直接访问特定对象或分片。

## 9.7 File Fingerprint

快速识别本地文件是否变化的摘要，不等同于完整文件 SHA-256。

## 9.8 Lifecycle

文件从可用到过期、归档和删除的状态及策略。

---

# 10. 数据模型

数据库使用 PostgreSQL。

## 10.1 file_objects

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | 文件 ID |
| `tenant_id` | String | 租户 |
| `principal_id` | String | 创建者 |
| `bucket` | String | Bucket |
| `object_key` | String | 对象 Key |
| `storage_backend` | Enum | local、s3 |
| `original_filename` | String | 原始文件名 |
| `size_bytes` | BigInt | 文件大小 |
| `content_type` | String | MIME |
| `etag` | String nullable | 存储 ETag |
| `checksum_algorithm` | String nullable | 校验算法 |
| `checksum_value` | String nullable | 校验值 |
| `file_fingerprint` | String nullable | 快速指纹 |
| `upload_id` | UUID nullable | 来源上传会话 |
| `metadata` | JSONB | 业务元数据 |
| `status` | Enum | active、deleted |
| `lifecycle_mode` | Enum | 生命周期模式 |
| `lifecycle_action` | Enum | 生命周期动作 |
| `lifecycle_status` | Enum | 生命周期状态 |
| `ttl_seconds` | BigInt nullable | TTL |
| `expires_at` | Timestamp nullable | 过期时间 |
| `next_action_at` | Timestamp nullable | 下次动作时间 |
| `last_accessed_at` | Timestamp nullable | 最近访问 |
| `legal_hold` | Boolean | Legal Hold |
| `retention_until` | Timestamp nullable | 最低保留时间 |
| `lifecycle_source` | String | 策略来源 |
| `delete_attempts` | Integer | 删除次数 |
| `completed_at` | Timestamp | 上传完成 |
| `deleted_at` | Timestamp nullable | 删除时间 |
| `created_at` | Timestamp | 创建时间 |
| `updated_at` | Timestamp | 更新时间 |

约束：

```text
UNIQUE(tenant_id, bucket, object_key)
```

## 10.2 upload_sessions

| 字段 | 类型 |
|---|---|
| `id` | UUID PK |
| `tenant_id` | String |
| `principal_id` | String |
| `backend` | Enum |
| `upload_mode` | Enum |
| `bucket` | String |
| `object_key` | String |
| `storage_upload_id` | String nullable |
| `original_filename` | String |
| `content_type` | String |
| `total_size` | BigInt |
| `part_size` | BigInt |
| `total_parts` | Integer |
| `file_fingerprint` | String nullable |
| `expected_sha256` | String nullable |
| `status` | Enum |
| `requested_lifecycle` | JSONB |
| `effective_lifecycle` | JSONB |
| `completed_file_id` | UUID nullable |
| `version` | Integer |
| `expires_at` | Timestamp |
| `last_activity_at` | Timestamp |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

## 10.3 upload_parts

| 字段 | 类型 |
|---|---|
| `id` | BigInt PK |
| `upload_id` | UUID FK |
| `part_number` | Integer |
| `offset_bytes` | BigInt |
| `size_bytes` | BigInt |
| `etag` | String nullable |
| `checksum_sha256` | String nullable |
| `status` | Enum |
| `attempt_count` | Integer |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

约束：

```text
UNIQUE(upload_id, part_number)
```

## 10.4 directory_upload_jobs

| 字段 | 类型 |
|---|---|
| `id` | UUID PK |
| `tenant_id` | String |
| `principal_id` | String |
| `source` | Enum |
| `root_directory_name` | String |
| `bucket` | String |
| `destination_prefix` | String |
| `status` | Enum |
| `conflict_policy` | Enum |
| `total_entries` | BigInt |
| `total_files` | BigInt |
| `total_directories` | BigInt |
| `total_bytes` | BigInt |
| `uploaded_files` | BigInt |
| `uploaded_bytes` | BigInt |
| `failed_files` | BigInt |
| `skipped_files` | BigInt |
| `manifest_hash` | String |
| `requested_lifecycle` | JSONB |
| `effective_lifecycle` | JSONB |
| `version` | Integer |
| `expires_at` | Timestamp |
| `completed_at` | Timestamp nullable |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

## 10.5 directory_upload_entries

| 字段 | 类型 |
|---|---|
| `id` | UUID PK |
| `directory_upload_id` | UUID FK |
| `entry_type` | Enum |
| `relative_path` | String |
| `normalized_path` | String |
| `object_key` | String |
| `size_bytes` | BigInt |
| `last_modified_ns` | BigInt nullable |
| `content_type` | String |
| `fingerprint` | String nullable |
| `full_sha256` | String nullable |
| `upload_id` | UUID nullable |
| `file_id` | UUID nullable |
| `status` | Enum |
| `error_code` | String nullable |
| `error_message` | String nullable |
| `requested_lifecycle` | JSONB nullable |
| `effective_lifecycle` | JSONB |
| `attempt_count` | Integer |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

约束：

```text
UNIQUE(directory_upload_id, normalized_path)
UNIQUE(directory_upload_id, object_key)
```

## 10.6 lifecycle_events

记录生命周期创建、修改、过期、删除和失败事件。

## 10.7 idempotency_records

记录：

```text
tenant_id
operation
idempotency_key
request_hash
response_status
response_body
expires_at
```

约束：

```text
UNIQUE(tenant_id, operation, idempotency_key)
```

## 10.8 webhook_outbox

采用 Transactional Outbox 模式保存待投递 Webhook。

---

# 11. 文件上传流程

## 11.1 小文件 Proxy 上传

```text
Client
→ POST /v1/files/upload
→ Auth
→ Streaming Read
→ StorageAdapter.put_object
→ 创建 file_objects
→ 返回文件信息
```

禁止完整读取文件到内存。

## 11.2 大文件 Presigned Multipart

```text
POST /v1/uploads
→ 创建上传会话

POST /v1/uploads/{id}/parts/presign
→ 返回分片 URL

Client PUT Part → S3/MinIO
→ 获取 ETag

POST /v1/uploads/{id}/parts/commit
→ 保存分片元数据

POST /v1/uploads/{id}/complete
→ 存储端对账
→ Complete Multipart
→ 创建 file_objects
```

## 11.3 Local Multipart

```text
/data/storage/.multipart/{upload_id}/parts/
├── 00000001.part
├── 00000002.part
└── 00000003.part
```

Complete 时依次合并，并通过原子 Rename 提交最终文件。

---

# 12. 断点续传

## 12.1 上传状态机

```text
initiated
→ uploading
→ completing
→ completed

initiated/uploading
→ aborting
→ aborted

initiated/uploading
→ expired

可恢复错误：
completing → uploading
```

## 12.2 恢复流程

```text
读取客户端本地状态
→ 校验本地文件
→ 查询服务端状态
→ 与存储端对账
→ 找出缺失分片
→ 重新获取预签名 URL
→ 上传缺失分片
→ Complete
```

## 12.3 文件指纹

快速指纹由以下信息生成：

```text
文件大小
文件修改时间
头部采样Hash
中间采样Hash
尾部采样Hash
```

需要强一致性时计算完整 SHA-256。

## 12.4 SDK 状态

文件上传状态：

```text
~/.pyuploadx/uploads/files/{upload_id}.json
```

目录上传状态：

```text
~/.pyuploadx/uploads/directories/{directory_upload_id}.sqlite3
```

状态中禁止保存：

- API Key；
- Bearer Token；
- S3 Access Key；
- S3 Secret Key；
- 长期预签名 URL。

## 12.5 重试策略

可重试：

```text
连接错误
超时
408
429
500
502
503
504
```

指数退避：

\[
delay=min(maxDelay, baseDelay \times 2^{attempt}) + jitter
\]

---

# 13. 目录上传

## 13.1 目录存储语义

Local 使用真实目录。

S3/MinIO 使用对象 Key 前缀：

```text
destination_prefix/images/cover.jpg
destination_prefix/videos/trailer.mp4
```

对象存储不存在真实目录。

## 13.2 路径安全

必须拒绝：

```text
../secret.txt
/absolute/path
C:\absolute\path
a/../../secret
NUL字符
控制字符
```

路径处理：

```text
转换为POSIX分隔符
→ Unicode NFC
→ 移除合法的 ./
→ 拒绝 ..
→ 拒绝绝对路径
→ 检查长度和层级
→ 检查归一化冲突
```

## 13.3 符号链接

默认：

```text
symlink_policy=ignore
```

可选：

```text
ignore
error
follow_files
follow_all
```

禁止链接逃逸目录根路径。

## 13.4 Manifest

小目录使用 JSON。

大目录使用 NDJSON：

```json
{"entry_type":"file","relative_path":"README.md","size_bytes":2048}
{"entry_type":"file","relative_path":"images/cover.jpg","size_bytes":5242880}
```

Manifest Hash 基于规范化并排序后的：

```text
relative_path
size_bytes
fingerprint
```

## 13.5 目录任务状态机

```text
created
→ manifest_uploading
→ ready
→ uploading
→ finalizing
→ completed

uploading
→ paused
→ uploading

uploading
→ cancelling
→ cancelled

finalizing
→ completed_with_errors
```

## 13.6 双层并发

```text
文件级并发：同时处理多少个文件
分片级并发：单个大文件同时上传多少个分片
全局并发：所有HTTP上传请求总上限
```

全局 Semaphore 必须限制理论并发。

## 13.7 冲突策略

| 策略 | 行为 |
|---|---|
| `reject` | 任一目标对象存在则拒绝 |
| `skip` | 跳过已存在对象 |
| `overwrite` | 覆盖 |
| `rename` | 自动生成新名称 |
| `compare` | 根据大小和校验值判断 |

默认：

```text
reject
```

## 13.8 空目录

默认不保留。

启用时，对象存储创建零字节目录标记：

```text
prefix/empty-directory/
```

---

# 14. 文件生命周期

## 14.1 生命周期模式

| 模式 | 说明 |
|---|---|
| `permanent` | 永久保存 |
| `ttl` | 完成后保留指定秒数 |
| `expires_at` | 指定 UTC 到期时间 |
| `temporary` | 临时文件语义 |
| `sliding_ttl` | 访问后续期 |

## 14.2 生命周期状态机

```text
active
→ expiring
→ expired
→ deleting
→ deleted

active
→ archiving
→ archived
→ restoring
→ active

任意自动删除前：
legal_hold 阻止执行
```

## 14.3 生命周期优先级

```text
Legal Hold
> 服务端强制策略
> 租户策略
> Bucket策略
> 文件级策略
> 目录级策略
> 服务默认策略
```

## 14.4 请求策略和生效策略

客户端提交：

```text
requested_lifecycle
```

服务端校验后返回：

```text
effective_lifecycle
```

服务端不得让客户端绕过：

- 最低保留期；
- 最大保留期；
- 永久保存限制；
- Legal Hold；
- Bucket 策略；
- 存储能力限制。

## 14.5 起始时间

单文件：

```text
expires_at = file.completed_at + ttl
```

目录支持：

```text
file_completed
directory_completed
```

默认：

```text
file_completed
```

## 14.6 Worker 执行

```text
查询 next_action_at <= now()
→ FOR UPDATE SKIP LOCKED
→ 检查 Legal Hold
→ 更新执行状态
→ 调用 StorageAdapter
→ 更新最终状态
→ 写 lifecycle_events
→ 投递 Webhook
```

---

# 15. Storage Adapter

## 15.1 接口

```python
from typing import BinaryIO, Protocol


class StorageAdapter(Protocol):
    capabilities: "StorageCapabilities"

    async def put_object(
        self,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        content_type: str | None,
        size_bytes: int | None,
    ) -> "StoredObject":
        ...

    async def get_object(
        self,
        bucket: str,
        object_key: str,
    ) -> "ObjectStream":
        ...

    async def delete_object(
        self,
        bucket: str,
        object_key: str,
    ) -> None:
        ...

    async def initiate_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        content_type: str | None,
        metadata: dict[str, str],
    ) -> str:
        ...

    async def upload_part(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        part_number: int,
        stream: BinaryIO,
        size_bytes: int,
        checksum_sha256: str | None,
    ) -> "UploadedPart":
        ...

    async def list_parts(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> list["UploadedPart"]:
        ...

    async def complete_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
        parts: list["UploadedPart"],
    ) -> "StoredObject":
        ...

    async def abort_multipart_upload(
        self,
        bucket: str,
        object_key: str,
        storage_upload_id: str,
    ) -> None:
        ...

    async def create_presigned_put_url(...):
        ...

    async def create_presigned_get_url(...):
        ...

    async def create_presigned_upload_part_url(...):
        ...
```

## 15.2 能力声明

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class StorageCapabilities:
    multipart: bool
    presigned_put: bool
    presigned_get: bool
    presigned_upload_part: bool
    list_parts: bool
    server_side_checksum: bool
    archive: bool
    transition: bool
    restore: bool
```

服务端根据能力选择上传和生命周期行为，不根据后端名称硬编码。

## 15.3 Local Adapter

要求：

- 路径规范化；
- 防路径逃逸；
- 流式读写；
- 临时文件；
- `fsync`；
- 原子 Rename；
- Multipart 临时目录；
- 集群模式共享文件系统。

## 15.4 S3 Adapter

统一支持：

- AWS S3；
- MinIO；
- 兼容 S3 的云对象存储。

配置差异：

- Endpoint；
- Region；
- Path Style；
- TLS；
- Credential；
- 公网和内网 Endpoint。

---

# 16. REST API

统一前缀：

```text
/v1
```

## 16.1 健康检查

```text
GET /healthz
GET /readyz
GET /startupz
GET /metrics
```

## 16.2 文件 API

```text
POST   /v1/files/upload
GET    /v1/files/{file_id}
GET    /v1/files/{file_id}/download
POST   /v1/files/{file_id}/presign-download
DELETE /v1/files/{file_id}
```

## 16.3 Presign API

```text
POST /v1/presign/put
POST /v1/presign/get
```

## 16.4 上传 API

```text
POST /v1/uploads
POST /v1/uploads/resume
GET  /v1/uploads/{upload_id}
GET  /v1/uploads/{upload_id}/parts

POST /v1/uploads/{upload_id}/parts/presign
PUT  /v1/uploads/{upload_id}/parts/{part_number}
POST /v1/uploads/{upload_id}/parts/commit

POST /v1/uploads/{upload_id}/refresh
POST /v1/uploads/{upload_id}/complete
POST /v1/uploads/{upload_id}/abort
```

创建上传：

```json
{
  "bucket": "app-default",
  "object_key": "models/model.bin",
  "original_filename": "model.bin",
  "content_type": "application/octet-stream",
  "total_size": 1073741824,
  "part_size": 8388608,
  "upload_mode": "automatic",
  "file_fingerprint": "sha256:...",
  "expected_sha256": null,
  "lifecycle": {
    "mode": "ttl",
    "ttl_seconds": 2592000,
    "action": "delete"
  },
  "metadata": {
    "business_type": "model"
  }
}
```

## 16.5 生命周期 API

```text
GET    /v1/files/{file_id}/lifecycle
PATCH  /v1/files/{file_id}/lifecycle
POST   /v1/files/{file_id}/lifecycle/extend
POST   /v1/files/{file_id}/lifecycle/make-permanent
POST   /v1/files/{file_id}/legal-hold
DELETE /v1/files/{file_id}/legal-hold
```

## 16.6 目录 API

```text
POST /v1/directory-uploads
POST /v1/directory-uploads/{id}/entries
POST /v1/directory-uploads/{id}/entries/stream
POST /v1/directory-uploads/{id}/manifest/complete

GET  /v1/directory-uploads/{id}
GET  /v1/directory-uploads/{id}/entries
GET  /v1/directory-uploads/{id}/manifest

POST  /v1/directory-uploads/{id}/entries/initiate
POST  /v1/directory-uploads/{id}/retry
POST  /v1/directory-uploads/{id}/complete
POST  /v1/directory-uploads/{id}/cancel
PATCH /v1/directory-uploads/{id}/lifecycle
```

## 16.7 Portal 配置

```text
GET /v1/client-config
```

返回当前身份允许的：

- 文件大小；
- 上传模式；
- 分片大小；
- 并发限制；
- MIME；
- 生命周期；
- 目录能力；
- 冲突策略。

## 16.8 错误格式

```json
{
  "error": {
    "code": "MISSING_PARTS",
    "message": "Upload cannot be completed.",
    "details": {
      "missing_parts": [4, 8, 9]
    },
    "retryable": false,
    "request_id": "req-123"
  }
}
```

## 16.9 主要错误码

```text
UPLOAD_NOT_FOUND
UPLOAD_ALREADY_COMPLETED
UPLOAD_ABORTED
UPLOAD_EXPIRED
UPLOAD_STATE_CONFLICT
INVALID_PART_NUMBER
INVALID_PART_SIZE
MISSING_PARTS
PART_ETAG_MISMATCH
CHECKSUM_MISMATCH
OBJECT_ALREADY_EXISTS
INVALID_RELATIVE_PATH
DUPLICATE_NORMALIZED_PATH
MANIFEST_INCOMPLETE
MANIFEST_HASH_MISMATCH
DIRECTORY_MANIFEST_MISMATCH
DIRECTORY_HAS_FAILED_ENTRIES
INVALID_LIFECYCLE_POLICY
TTL_OUT_OF_RANGE
FILE_UNDER_LEGAL_HOLD
STORAGE_CAPABILITY_NOT_SUPPORTED
STORAGE_UNAVAILABLE
DATABASE_UNAVAILABLE
```

---

# 17. Python Client SDK

## 17.1 基础用法

```python
from pyuploadx import UploadClient

client = UploadClient(
    base_url="https://uploads.example.com",
    bearer_token="...",
    state_dir="~/.pyuploadx/uploads",
)

result = client.upload_file(
    "./README.md",
    bucket="app-default",
)
```

## 17.2 大文件

```python
result = client.upload_large_file(
    file_path="./model.bin",
    bucket="app-default",
    object_key="models/model.bin",
    part_size=8 * 1024 * 1024,
    concurrency=4,
    resume=True,
)
```

## 17.3 生命周期

```python
from datetime import timedelta
from pyuploadx.lifecycle import FileLifecycle

result = client.upload_file(
    "./report.pdf",
    lifecycle=FileLifecycle.ttl(
        timedelta(days=30),
    ),
)
```

支持：

```python
FileLifecycle.permanent()
FileLifecycle.temporary(timedelta(hours=24))
FileLifecycle.ttl(timedelta(days=30))
FileLifecycle.expires_at(datetime_value)
FileLifecycle.sliding_ttl(timedelta(days=7))
```

## 17.4 目录上传

```python
result = client.upload_directory(
    directory_path="./album-assets",
    bucket="app-default",
    destination_prefix="artists/10001/albums/2026",
    recursive=True,
    resume=True,
    file_concurrency=8,
    part_concurrency=4,
    include=["**/*"],
    exclude=[
        ".git/**",
        "**/.DS_Store",
        "**/*.tmp",
    ],
    symlink_policy="ignore",
    conflict_policy="reject",
    lifecycle=FileLifecycle.ttl(
        timedelta(days=30),
    ),
)
```

## 17.5 SDK 异常

```text
UploadClientError
AuthenticationError
AuthorizationError
ValidationError
RateLimitError
ServerError
StorageUnavailableError
MultipartError
ResumeError
DirectoryUploadError
LifecycleError
ChecksumMismatchError
```

## 17.6 SDK 包结构

```text
pyuploadx/
├── client.py
├── models.py
├── exceptions.py
├── retry.py
├── fingerprint.py
├── lifecycle.py
├── state.py
├── multipart.py
├── directory.py
├── directory_state.py
├── manifest.py
├── ignore.py
├── paths.py
└── scheduler.py
```

---

# 18. Portal

## 18.1 技术选型

```text
React
TypeScript
Vite
Dexie
IndexedDB
Web Crypto API
OpenAPI Generated Client
```

## 18.2 页面功能

- 文件拖放；
- 文件选择；
- 目录选择；
- 多文件上传；
- 上传队列；
- 文件树；
- 生命周期选择；
- Bucket 和目标前缀；
- 上传模式；
- 整体和文件级进度；
- 暂停；
- 继续；
- 取消；
- 失败重试；
- 完成结果；
- 下载链接。

## 18.3 目录选择

```html
<input type="file" webkitdirectory multiple />
```

同时支持：

- 拖放目录；
- 多文件选择降级；
- 浏览器能力检测。

## 18.4 Portal 恢复

IndexedDB 保存：

```text
directoryJobs
directoryEntries
fileUploads
uploadParts
```

页面刷新后：

```text
恢复任务元数据
→ 提示重新选择原文件或目录
→ 校验指纹
→ 查询服务端状态
→ 上传缺失内容
```

## 18.5 鉴权

Portal 推荐使用：

```text
OIDC Authorization Code + PKCE
```

不得把长期 API Key 写入浏览器代码或 LocalStorage。

---

# 19. YAML 配置

## 19.1 优先级

```text
代码默认值
< YAML
< 环境变量
< 命令行参数
```

嵌套环境变量：

```text
UPLOAD_SERVER__PORT=8080
```

## 19.2 配置示例

```yaml
app:
  name: upload-service
  environment: development
  version: "1.4.0"
  debug: false

server:
  host: 0.0.0.0
  port: 8000
  workers: 2
  proxy_headers: true

  timeouts:
    request_seconds: 300
    keep_alive_seconds: 10
    graceful_shutdown_seconds: 60

auth:
  mode: api_key

  api_key:
    header_name: X-API-Key
    keys_from_env: UPLOAD_API_KEYS

database:
  url_from_env: UPLOAD_DATABASE_URL
  pool_size: 20
  max_overflow: 20
  pool_timeout_seconds: 30
  pool_recycle_seconds: 1800

redis:
  enabled: true
  url_from_env: UPLOAD_REDIS_URL
  key_prefix: upload-service

storage:
  backend: s3
  default_bucket: app-default

  allowed_buckets:
    - app-default
    - public-assets

  local:
    root_path: /data/storage
    multipart_path: /data/storage/.multipart
    require_shared_filesystem_in_cluster: true
    fsync: true

  s3:
    internal_endpoint_url: http://minio:9000
    public_endpoint_url: http://localhost:9000
    region: us-east-1
    access_key_from_env: S3_ACCESS_KEY
    secret_key_from_env: S3_SECRET_KEY
    force_path_style: true
    use_ssl: false
    verify_ssl: false
    max_pool_connections: 100

uploads:
  default_mode: automatic
  direct_upload_threshold_bytes: 20971520
  object_conflict_policy: reject

  multipart:
    enabled: true
    default_part_size_bytes: 8388608
    minimum_part_size_bytes: 5242880
    maximum_part_size_bytes: 536870912
    maximum_parts: 10000
    maximum_presign_batch_size: 100

  session:
    expires_after_seconds: 86400
    maximum_lifetime_seconds: 604800
    refresh_enabled: true

  file_size:
    maximum_bytes: 5368709120

presign:
  default_expires_seconds: 900
  maximum_expires_seconds: 86400
  upload_part_expires_seconds: 3600

directory_upload:
  enabled: true

  limits:
    maximum_files_per_job: 1000000
    maximum_directories_per_job: 100000
    maximum_total_bytes: 1099511627776
    maximum_path_depth: 64
    maximum_relative_path_bytes: 1024
    maximum_entries_per_manifest_request: 1000

  upload:
    default_file_concurrency: 8
    maximum_file_concurrency: 32
    default_part_concurrency: 4
    maximum_part_concurrency: 16
    maximum_total_concurrent_requests: 32

  ignore:
    file_name: .uploadignore
    defaults:
      - ".git/**"
      - "**/.DS_Store"
      - "**/__pycache__/**"
      - "**/*.tmp"

  symlinks:
    policy: ignore
    allow_outside_root: false
    detect_cycles: true

  conflicts:
    default_policy: reject
    allowed_policies:
      - reject
      - skip
      - overwrite
      - rename
      - compare

  lifecycle:
    allow_entry_override: true
    starts_at: file_completed

lifecycle:
  enabled: true

  default_policy:
    mode: ttl
    ttl_seconds: 2592000
    action: delete

  policy:
    allow_client_override: true
    permanent_allowed: true
    minimum_ttl_seconds: 3600
    maximum_ttl_seconds: 31536000

    allowed_modes:
      - temporary
      - ttl
      - expires_at
      - permanent
      - sliding_ttl

    allowed_actions:
      - delete
      - notify
      - none

  worker:
    enabled: true
    scan_interval_seconds: 60
    batch_size: 200
    concurrency: 8

portal:
  enabled: true
  public_base_url: https://upload.example.com

  origins:
    - https://upload.example.com

  cors:
    allow_credentials: true
    allow_methods:
      - GET
      - POST
      - PUT
      - PATCH
      - DELETE
      - OPTIONS
    allow_headers:
      - Authorization
      - Content-Type
      - X-API-Key
      - Idempotency-Key
      - X-Part-SHA256
      - X-Request-ID
    expose_headers:
      - ETag
      - X-Request-ID

cluster:
  enabled: true
  node_id_from_env: HOSTNAME

  readiness:
    check_database: true
    check_redis: true
    check_storage: true

worker:
  enabled: true

  cleanup:
    enabled: true
    interval_seconds: 300
    batch_size: 100

logging:
  level: INFO
  format: json

  redact_headers:
    - Authorization
    - X-API-Key
    - Cookie

metrics:
  enabled: true
  path: /metrics

tracing:
  enabled: false
  service_name: upload-service
  otlp_endpoint: null
```

## 19.3 配置命令

```bash
python -m upload_service config validate
python -m upload_service config show --redact-secrets
```

集群模式必须拒绝 SQLite。

---

# 20. 集群与一致性

## 20.1 无状态节点

以下请求可以进入不同节点：

```text
Initiate → Node 1
Presign  → Node 2
Commit   → Node 3
Complete → Node 1
```

## 20.2 数据库锁

Complete、Abort、Cancel 和生命周期修改必须使用：

```sql
SELECT *
FROM upload_sessions
WHERE id = :upload_id
FOR UPDATE;
```

## 20.3 Worker 领取任务

```sql
SELECT id
FROM lifecycle_tasks
WHERE available_at <= NOW()
  AND status = 'pending'
FOR UPDATE SKIP LOCKED
LIMIT 100;
```

## 20.4 Part Upsert

```sql
INSERT INTO upload_parts (...)
VALUES (...)
ON CONFLICT (upload_id, part_number)
DO UPDATE SET
  etag = EXCLUDED.etag,
  size_bytes = EXCLUDED.size_bytes,
  status = EXCLUDED.status,
  updated_at = NOW();
```

## 20.5 Complete 幂等

重复 Complete：

- 不重复调用存储完成操作；
- 不重复创建 `file_objects`；
- 返回同一个 `file_id`；
- 响应丢失后允许安全重试。

## 20.6 Redis 的角色

Redis 锁只能减少重复工作。

最终正确性依赖：

```text
PostgreSQL事务
状态机
唯一约束
幂等记录
存储端对账
```

---

# 21. 后台任务

Worker 负责：

- 过期上传会话；
- 未完成 Multipart；
- Local 临时目录；
- 生命周期删除；
- 归档和恢复；
- Webhook；
- 目录进度聚合；
- 孤儿对象；
- 数据库和存储端对账；
- 过期幂等记录。

对账命令：

```bash
python -m upload_service reconcile upload {upload_id} --dry-run
python -m upload_service reconcile file {file_id} --dry-run
python -m upload_service reconcile directory {directory_id} --dry-run
```

---

# 22. 安全设计

## 22.1 鉴权

SDK：

```text
X-API-Key
或
OAuth2 Client Credentials
```

Portal：

```text
OIDC Authorization Code + PKCE
```

## 22.2 权限

```text
files:upload
files:read
files:download
files:delete
files:lifecycle:read
files:lifecycle:update
files:lifecycle:permanent
files:legal-hold
uploads:resume
uploads:abort
directories:upload
directories:cancel
```

## 22.3 对象 Key

建议存储 Key：

```text
{tenant_id}/{yyyy}/{mm}/{dd}/{uuid}/{safe_filename}
```

禁止客户端逃逸租户路径。

## 22.4 Presigned URL

- 短 TTL；
- 指定方法；
- 绑定 Bucket 和 Key；
- 绑定 Upload ID 和 Part Number；
- 不记录完整 URL；
- 不持久化 URL；
- 下载 URL 不超过文件剩余生命周期。

## 22.5 CORS

FastAPI 和对象存储必须配置明确 Origin。

对象存储必须暴露：

```text
ETag
```

## 22.6 HTTPS

生产环境强制 HTTPS，并配置：

- TLS；
- HSTS；
- HTTP 跳转 HTTPS；
-可信代理列表；
-真实客户端 IP；
-请求大小和连接限制。

---

# 23. 可观测性

## 23.1 日志

结构化日志字段：

```text
timestamp
level
request_id
trace_id
node_id
tenant_id
principal_id
upload_id
directory_upload_id
file_id
part_number
backend
operation
duration_ms
error_code
```

不得记录：

- Secret；
-完整 Authorization；
-完整 API Key；
-完整预签名 URL。

## 23.2 指标

```text
upload_requests_total
upload_latency_seconds
upload_active_sessions
upload_parts_total
upload_part_bytes_total
upload_part_retries_total
upload_resume_total
upload_complete_total
upload_abort_total
upload_expired_total
upload_checksum_failures_total

directory_upload_jobs_total
directory_upload_active_jobs
directory_upload_entries_total
directory_upload_bytes_total
directory_manifest_processing_seconds
directory_upload_failed_files_total

lifecycle_actions_total
lifecycle_action_failures_total
lifecycle_pending_files
lifecycle_action_latency_seconds

database_pool_in_use
database_lock_wait_seconds
redis_operation_latency_seconds
storage_operation_latency_seconds
```

禁止使用高基数字段作为 Prometheus Label。

## 23.3 健康检查

Liveness：

```text
GET /healthz
```

Readiness：

```text
GET /readyz
```

Startup：

```text
GET /startupz
```

---

# 24. 单节点部署

![单节点部署](assets/png/single-node-deployment.png)

## 24.1 组件

```text
Nginx
Portal
FastAPI
Worker
PostgreSQL
Redis
MinIO
```

## 24.2 启动

```bash
docker compose \
  -f deploy/single-node/compose.yaml \
  up -d --build
```

## 24.3 持久化

```text
/var/lib/upload-service/
├── postgres/
├── redis/
├── minio/
├── local-storage/
├── backups/
└── certificates/
```

## 24.4 使用场景

- 开发；
- 测试；
- 小型内部系统；
- 不要求节点级高可用。

---

# 25. 集群部署

![集群部署](assets/png/cluster-deployment.png)

## 25.1 组件建议

```text
Gateway：1个外部LB或2个Gateway
FastAPI：3个节点
Worker：2个以上
PostgreSQL
Redis
MinIO/S3
Portal
Prometheus
Grafana
```

## 25.2 启动

```bash
docker compose \
  -f deploy/cluster/compose.yaml \
  up -d --build \
  --scale api=3 \
  --scale worker=2
```

## 25.3 集群约束

- 不使用 SQLite；
- 不依赖 Sticky Session；
- Local 后端必须共享文件系统；
- 所有节点使用相同配置；
- 所有节点访问相同数据库和存储；
- 节点故障后 SDK/Portal 自动重试。

---

# 26. Kubernetes 部署

## 26.1 资源

```text
Deployment/upload-api
Deployment/upload-worker
Deployment/upload-portal

Service/upload-api
Service/upload-portal

Ingress/upload-public
ConfigMap/upload-config
Secret/upload-secrets

HPA/upload-api
HPA/upload-worker

PDB/upload-api
PDB/upload-worker

ServiceMonitor/upload-api
```

## 26.2 API Deployment

建议：

```text
replicas: 3
maxUnavailable: 0
maxSurge: 1
terminationGracePeriodSeconds: 60
```

## 26.3 优雅终止

```text
SIGTERM
→ Readiness失败
→ 停止接收新请求
→ 等待当前短请求
→ Proxy Part失败时客户端重试
→ Presigned上传不受影响
→ 关闭连接
```

## 26.4 调度

API 副本分布在不同：

```text
kubernetes.io/hostname
topology.kubernetes.io/zone
```

---

# 27. 生产组网

![生产组网](assets/png/network-topology.png)

## 27.1 网络区域

```text
公网区
接入区/DMZ
应用区
数据区
管理区
```

## 27.2 网络矩阵

| 来源 | 目标 | 端口 | 允许 |
|---|---|---:|---|
| Internet | Gateway | 443 | 是 |
| Browser | Object Storage API | 443/9000 | 仅预签名 |
| Gateway | Portal | 80 | 是 |
| Gateway | FastAPI | 8000 | 是 |
| FastAPI | PostgreSQL | 5432 | 是 |
| FastAPI | Redis | 6379 | 是 |
| FastAPI | S3/MinIO | 443/9000 | 是 |
| Worker | PostgreSQL | 5432 | 是 |
| Worker | Redis | 6379 | 是 |
| Worker | S3/MinIO | 443/9000 | 是 |
| Internet | PostgreSQL | 5432 | 否 |
| Internet | Redis | 6379 | 否 |
| Internet | MinIO Console | 9001 | 否 |

## 27.3 内外 Endpoint

```yaml
storage:
  s3:
    internal_endpoint_url: http://minio:9000
    public_endpoint_url: https://objects.example.com
```

返回浏览器的预签名 URL 必须使用浏览器可访问的地址。

---

# 28. 备份、恢复、升级和回滚

## 28.1 PostgreSQL

- 每日全量备份；
- WAL 归档；
- Point-in-time Recovery；
- 至少保留 30 天；
- 定期恢复演练。

## 28.2 对象存储

按业务要求启用：

- Versioning；
-跨区域复制；
-对象锁；
-生命周期；
-外部备份。

## 28.3 恢复顺序

```text
恢复PostgreSQL
→ 恢复对象存储
→ 启动Redis
→ 启动API只读检查
→ Reconcile Dry Run
→ 修复差异
→ 启动Worker
→ 开放上传入口
```

## 28.4 数据库迁移

```text
执行向后兼容Migration
→ 部署新API
→ 滚动替换旧节点
→ 确认无旧版本
→ 清理废弃字段
```

## 28.5 回滚

回滚必须保证：

- 数据库 Schema 向后兼容；
- 上传会话不绑定应用版本；
- SDK/API v1 保持兼容；
- 旧节点可以读取新版本期间创建的基础会话。

---

# 29. 测试方案

## 29.1 单元测试

- 配置；
- 路径规范化；
- 状态机；
- 生命周期策略；
- Storage Adapter 契约；
- 指纹；
- 重试；
- 幂等。

## 29.2 集成测试

- Local；
- MinIO；
- Proxy；
- Presigned；
- Multipart；
- Complete；
- Abort；
- 生命周期；
- 目录 Manifest；
- Portal CORS。

## 29.3 断点测试

- 上传 30% 后退出；
- URL 过期；
- API 节点退出；
- SDK 状态丢失；
- 文件变化；
- Complete 响应丢失；
- 重复分片；
- 分片损坏。

## 29.4 目录测试

- 嵌套目录；
- 空目录；
- Unicode；
- Windows 路径；
- `.uploadignore`；
- 符号链接；
- 路径穿越；
- Manifest 冲突；
- 单文件失败；
- 目录恢复；
- 生命周期继承。

## 29.5 集群测试

```text
3个API
2个Worker
停止随机API
停止随机Worker
Complete并发
Abort并发
Complete与Abort并发
Worker重复领取
Readiness摘除
```

## 29.6 Portal E2E

使用 Playwright 测试：

- 登录；
- 文件上传；
- 目录上传；
-暂停；
-恢复；
-刷新页面；
-生命周期；
-错误展示；
-CORS；
-Token过期。

## 29.7 性能测试

```text
100并发小文件
1 GiB分片文件
100,000个1 KiB文件
10,000个混合文件
目录总大小1 TiB
64层目录
```

---

# 30. 性能与容量规划

## 30.1 数据库连接

\[
Connections =
ApiReplicas \times ApiPool
+
WorkerReplicas \times WorkerPool
+
Reserved
\]

禁止随 API 扩容无限放大连接池。

## 30.2 写入优化

- 分片批量 Upsert；
- Manifest 批量 Insert；
- 目录进度定期聚合；
- 不逐字节更新数据库；
- 使用 Cursor Pagination；
- 审计数据定期归档。

## 30.3 大量小文件

优化：

- 批量 Manifest；
- 批量创建会话；
- 批量查询状态；
- HTTP Keep-Alive；
- 连接池；
- 文件并发；
- 批量完成结果；
- Redis 进度缓存。

---

# 31. 项目目录

```text
upload-service/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── dependencies.py
│   │   └── v1/
│   │       ├── files.py
│   │       ├── uploads.py
│   │       ├── directory_uploads.py
│   │       ├── lifecycle.py
│   │       ├── presign.py
│   │       ├── client_config.py
│   │       └── health.py
│   ├── config/
│   │   ├── loader.py
│   │   ├── models.py
│   │   └── validation.py
│   ├── core/
│   │   ├── auth.py
│   │   ├── errors.py
│   │   ├── idempotency.py
│   │   ├── logging.py
│   │   ├── metrics.py
│   │   └── tracing.py
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   ├── repositories/
│   │   └── migrations/
│   ├── storage/
│   │   ├── base.py
│   │   ├── capabilities.py
│   │   ├── local.py
│   │   └── s3.py
│   ├── services/
│   │   ├── file_service.py
│   │   ├── upload_service.py
│   │   ├── directory_upload_service.py
│   │   ├── lifecycle_service.py
│   │   ├── cleanup_service.py
│   │   ├── reconcile_service.py
│   │   └── webhook_service.py
│   ├── directory_upload/
│   │   ├── manifest.py
│   │   ├── paths.py
│   │   ├── state_machine.py
│   │   └── aggregation.py
│   ├── lifecycle/
│   │   ├── policy.py
│   │   ├── state_machine.py
│   │   └── executor.py
│   └── worker/
│       ├── main.py
│       ├── cleanup.py
│       ├── lifecycle.py
│       ├── directory.py
│       ├── reconcile.py
│       └── webhook.py
├── sdk/
│   └── pyuploadx/
│       ├── client.py
│       ├── models.py
│       ├── exceptions.py
│       ├── fingerprint.py
│       ├── retry.py
│       ├── state.py
│       ├── lifecycle.py
│       ├── multipart.py
│       ├── directory.py
│       ├── directory_state.py
│       ├── manifest.py
│       ├── ignore.py
│       ├── paths.py
│       └── scheduler.py
├── portal/
│   ├── src/
│   │   ├── api/
│   │   ├── upload/
│   │   ├── directory-upload/
│   │   ├── components/
│   │   └── pages/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── config/
│   └── config.yaml
├── deploy/
│   ├── single-node/
│   ├── cluster/
│   ├── kubernetes/
│   ├── nginx/
│   └── minio/
├── docs/
│   ├── product-design.md
│   ├── deployment.md
│   └── assets/
│       ├── svg/
│       └── png/
├── scripts/
│   └── render_diagrams.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── directory/
│   ├── lifecycle/
│   ├── cluster/
│   ├── portal/
│   ├── security/
│   ├── performance/
│   └── e2e/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── README.md
```

---

# 32. 实施计划

## 阶段一：基础上传

- FastAPI 工程；
- YAML 配置；
- PostgreSQL；
- Local/S3 Adapter；
- 单文件上传下载；
- API Key；
- Docker Compose。

## 阶段二：Multipart 和 SDK

- 上传会话；
- 分片 API；
- Presigned；
- SDK；
- 重试；
- 断点续传；
- MinIO 集成测试。

## 阶段三：集群

- Redis；
- 幂等；
- 数据库锁；
- Worker；
- 多 API 节点；
- Cleanup；
- Reconcile；
- 集群测试。

## 阶段四：生命周期

- 生命周期模型；
- Lifecycle API；
- Worker；
- Legal Hold；
- Webhook；
- 审计。

## 阶段五：Portal

- React Portal；
- Proxy；
- Presigned；
- IndexedDB；
- 暂停和恢复；
- 生命周期 UI。

## 阶段六：目录上传

- Manifest；
- NDJSON；
- SDK 目录上传；
- Portal 目录上传；
- 目录断点续传；
- 大量小文件优化。

## 阶段七：生产部署

- Kubernetes；
- HPA；
- PDB；
- 监控；
- 备份；
- SVG/PNG 文档；
- 性能和安全测试。

---

# 33. Codex 开发任务

## Task A：工程脚手架

- FastAPI；
- SQLAlchemy；
- Alembic；
- Pydantic Settings；
- 统一错误处理；
- 请求 ID；
- 日志。

## Task B：配置系统

- YAML；
- 环境变量覆盖；
- Secret 引用；
- 严格校验；
- Config CLI。

## Task C：Storage Adapter

- Protocol；
- Capabilities；
- Local；
- S3/MinIO；
- Contract Tests。

## Task D：基础文件 API

- 上传；
- 下载；
- 删除；
- Metadata；
- Presign。

## Task E：Multipart

- Upload Session；
- Part；
- Complete；
- Abort；
- 对账；
- 幂等。

## Task F：Python SDK

- UploadClient；
- 文件上传；
- 大文件；
- 重试；
- 状态；
- 进度。

## Task G：断点续传

- 指纹；
- 本地状态；
- 服务端状态对账；
- URL 刷新；
- Resume API。

## Task H：集群一致性

- PostgreSQL 行锁；
- Upsert；
- Redis；
- 多节点测试；
- 无 Sticky Session。

## Task I：生命周期

- 数据模型；
- 策略；
- API；
- Worker；
- Legal Hold；
- Webhook。

## Task J：Portal

- React；
- OpenAPI Client；
- 文件上传；
- IndexedDB；
- 暂停恢复；
- 生命周期 UI。

## Task K：目录上传

- Manifest；
- 路径规范化；
- NDJSON；
- 目录状态机；
- 批量 API；
- SDK；
- Portal。

## Task L：后台任务

- Cleanup；
- Lifecycle；
- Directory Aggregation；
- Reconcile；
- Webhook Outbox。

## Task M：部署

- 单节点 Compose；
- 集群 Compose；
- Kubernetes；
- Nginx；
- MinIO Bootstrap；
- CORS。

## Task N：可观测性

- Prometheus；
- OpenTelemetry；
-日志；
-告警；
-Grafana Dashboard。

## Task O：文档图

- SVG 源文件；
- PNG 生成；
- Markdown 引用；
- CI 校验。

---

# 34. Definition of Done

## 基础能力

- [ ] Docker Compose 可以一键启动；
- [ ] Local、S3、MinIO Adapter 可用；
- [ ] 支持文件上传、下载和删除；
- [ ] 支持 Proxy 和 Presigned；
- [ ] 支持 Multipart；
- [ ] 支持 Python SDK；
- [ ] OpenAPI 完整。

## 断点续传

- [ ] SDK 退出后可以继续；
- [ ] Portal 刷新后可以恢复；
- [ ] URL 过期可以刷新；
- [ ] API 节点退出不丢失状态；
- [ ] Complete 和 Abort 幂等；
- [ ] 只重传缺失分片。

## 目录上传

- [ ] SDK 支持递归目录；
- [ ] Portal 支持选择和拖放目录；
- [ ] 保留相对路径；
- [ ] 支持 Manifest；
- [ ] 支持 NDJSON；
- [ ] 支持 `.uploadignore`；
- [ ] 防路径穿越；
- [ ] 支持目录恢复；
- [ ] 单文件失败不影响成功文件；
- [ ] 支持目录生命周期。

## 生命周期

- [ ] SDK 可以设置生命周期；
- [ ] Portal 可以选择生命周期；
- [ ] 返回最终生效策略；
- [ ] Worker 支持多副本；
- [ ] 删除幂等；
- [ ] 支持续期；
- [ ] 支持 Legal Hold；
- [ ] 提供审计事件。

## 集群

- [ ] 支持 3 个 API 节点；
- [ ] 支持 2 个 Worker；
- [ ] 不依赖 Sticky Session；
- [ ] 集群禁止 SQLite；
- [ ] Local 集群要求共享存储；
- [ ] Readiness 可摘除故障节点；
- [ ] 节点退出后上传可继续。

## 安全

- [ ] 生产强制 HTTPS；
- [ ] CORS 使用明确 Origin；
- [ ] Secret 不写入配置仓库；
- [ ] 日志不泄露密钥和完整签名 URL；
- [ ] 数据库和 Redis 不公开；
- [ ] 对象 Key 防路径逃逸；
- [ ] 上传会话校验所有权。

## 部署和文档

- [ ] 单节点部署文档；
- [ ] 集群部署文档；
- [ ] Kubernetes 模板；
- [ ] 生产组网图；
- [ ] SVG 自动生成 PNG；
- [ ] Markdown 引用 PNG；
- [ ] CI 验证图形同步；
- [ ] 备份和恢复文档；
- [ ] 性能和故障测试。

---

# 35. 架构图生成规范

## 35.1 文件约定

```text
docs/assets/svg/
├── system-architecture.svg
├── single-node-deployment.svg
├── cluster-deployment.svg
└── network-topology.svg

docs/assets/png/
├── system-architecture.png
├── single-node-deployment.png
├── cluster-deployment.png
└── network-topology.png
```

SVG 是源文件，PNG 是生成文件。

## 35.2 Markdown 引用

```markdown
![系统总体架构](assets/png/system-architecture.png)
![单节点部署](assets/png/single-node-deployment.png)
![集群部署](assets/png/cluster-deployment.png)
![生产组网](assets/png/network-topology.png)
```

## 35.3 生成脚本

```python
from pathlib import Path

import cairosvg


SOURCE_DIR = Path("docs/assets/svg")
OUTPUT_DIR = Path("docs/assets/png")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for source in sorted(SOURCE_DIR.glob("*.svg")):
        destination = OUTPUT_DIR / f"{source.stem}.png"
        temporary = destination.with_suffix(".png.tmp")

        cairosvg.svg2png(
            url=str(source),
            write_to=str(temporary),
            output_width=1800,
        )

        temporary.replace(destination)


if __name__ == "__main__":
    main()
```

## 35.4 Makefile

```makefile
.PHONY: diagrams diagrams-force docs-check

diagrams:
	python scripts/render_diagrams.py

diagrams-force:
	python scripts/render_diagrams.py --force

docs-check:
	python scripts/render_diagrams.py --check
```

## 35.5 CI

CI 必须：

- 渲染所有 SVG；
- 验证 PNG 已提交；
- 验证 PNG 不落后于 SVG；
- 验证 Markdown 引用文件存在；
- 禁止 SVG 外部脚本和本地绝对路径。

---

# 36. 最终技术决策

## 开发环境

```text
FastAPI
+ PostgreSQL
+ Redis
+ MinIO
+ Python SDK
+ React Portal
+ Docker Compose
```

## 小规模部署

```text
Nginx
+ 2～3个FastAPI实例
+ 1～2个Worker
+ PostgreSQL
+ Redis
+ MinIO
```

## 生产部署

```text
WAF / Load Balancer
+ Kubernetes Ingress
+ 3个以上FastAPI副本
+ 多副本Worker
+ PostgreSQL HA
+ Redis HA
+ S3或MinIO分布式集群
+ Prometheus/Grafana
+ OpenTelemetry
+ 集中日志
```

## 核心结论

1. FastAPI 负责控制面，不应默认承担全部大文件流量。
2. 大文件和目录上传优先使用 S3 Multipart 与预签名 URL。
3. PostgreSQL 是上传、目录和生命周期状态的权威数据源。
4. API 节点保持无状态，不依赖 Sticky Session。
5. SDK 和 Portal 都必须支持断点续传。
6. 目录上传使用 Manifest 和独立文件上传会话。
7. 生命周期从文件完成上传后开始计算。
8. SDK 和 Portal 请求的生命周期必须经过服务端策略裁决。
9. Local 集群模式必须使用共享文件系统。
10. Complete、Abort、Cancel、删除和 Webhook 必须幂等。
11. 配置通过 YAML 管理，Secret 通过环境变量注入。
12. 架构图以 SVG 为源文件，生成 PNG 后嵌入 Markdown。


---

# 37. 发布与版本管理

SDK 与服务端拆分为两个独立发布包：

- `pyuploadx`：Python 客户端 SDK（构建于 `sdk/pyuploadx/`，第三方依赖仅 `httpx`）。
- `pyuploadx-server`：FastAPI 服务端（构建于仓库根，包含 `app/` 与 `upload_service/`）。

## 37.1 发布目标

- **PyPI**：`pip install pyuploadx` / `pip install pyuploadx-server`。
- **仓库发布产物**：`dist/` 保存全部历史版本的 wheel 与 sdist，随仓库提交并推送
  `origin`（GitHub）与 `tiancloud`（内部镜像），不得清理旧版本。
- 每次发版打标签（SDK `vX.Y.Z`，服务端 `server-vX.Y.Z`），并同步更新
  `dist/README.md` 版本索引。

## 37.2 版本号

- SDK：`sdk/pyuploadx/pyproject.toml` 的 `version`，与 `sdk/pyuploadx/__init__.py` 的
  `__version__` 保持一致。
- 服务端：根 `pyproject.toml` 的 `version`。
- `scripts/publish-pypi.sh` 支持 `PYUPX_VERSION`、`scripts/publish-pypi-server.sh` 支持
  `PYUPX_SERVER_VERSION` 临时覆盖版本（发布后自动还原）。

## 37.3 发布步骤

1. 更新对应包的版本号。
2. `cp config/pypi.env.example config/pypi.env`，填入 PyPI API Token
   （`config/pypi.env` 已被 `.gitignore` 排除，禁止入库）。
3. `bash scripts/publish-pypi.sh` 发布 SDK；`bash scripts/publish-pypi-server.sh`
   发布服务端。两者均：构建 wheel/sdist 到 `dist/`（保留历史）并上传 PyPI；
   `--test` 上传 TestPyPI，`--skip-build` 复用已有产物。
4. 提交 `dist/` 产物与文档变更，打标签，推送分支与标签到两个远程仓库。

## 37.4 产物验证

- `twine check dist/*` 校验元数据与描述渲染。
- 安装验证：`pip install dist/pyuploadx-X.Y.Z-py3-none-any.whl` 后
  `import pyuploadx` 并检查 `__version__`；服务端同理验证 `pyuploadx_server` 包。
