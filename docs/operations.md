# PyUploadX 运维手册

运维操作对应产品设计说明书 §28（备份、恢复、升级、回滚）。

## 备份

### PostgreSQL

- 每日全量备份：`pg_dump -Fc -h <host> -U upload uploads -f uploads_$(date +%F).dump`。
- 生产建议开启 WAL 归档并启用 Point-in-Time Recovery，备份至少保留 30 天。
- 定期执行恢复演练（见下）。

### 对象存储

按业务要求为存储桶启用：版本控制（Versioning）、跨区域复制、对象锁（Object Lock）、
生命周期规则，以及外部备份。

## 恢复顺序

```text
恢复 PostgreSQL
→ 恢复对象存储
→ 启动 Redis
→ 启动 API 只读检查（/readyz）
→ Reconcile Dry Run（python -m upload_service reconcile ... --dry-run）
→ 修复差异
→ 启动 Worker
→ 开放上传入口
```

```bash
# 恢复 PostgreSQL 全量备份
pg_restore -h <host> -U upload -d uploads --clean --if-exists uploads_2026-08-26.dump
```

## 数据库迁移

```bash
alembic upgrade head      # 升级到最新 schema
alembic downgrade -1      # 回退一个版本（仅限向后兼容的迁移）
```

升级顺序（§28.4）：

```text
执行向后兼容 Migration
→ 部署新 API
→ 滚动替换旧节点
→ 确认无旧版本
→ 清理废弃字段
```

## 回滚

回滚必须保证（§28.5）：

- 数据库 Schema 向后兼容；
- 上传会话不绑定应用版本；
- SDK/API v1 保持兼容；
- 旧节点可以读取新版本期间创建的基础会话。

因此回滚只回退应用镜像，不回退数据库；仅在迁移被设计为可逆时才执行
`alembic downgrade`。
