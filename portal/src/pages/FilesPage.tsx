import { useCallback, useEffect, useState } from "react";
import { App, Button, Input, InputNumber, Modal, Select, Space, Spin, Table, Tag, Tooltip } from "antd";
import {
  Download,
  FolderPlus,
  Link2,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Trash2,
} from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import * as api from "../api/client";
import { BucketTree } from "../components/BucketTree";

interface Props {
  config: api.ClientConfig;
  onLogout: () => void;
  onConfigRefresh: () => Promise<void>;
}

const PAGE_SIZE = 50;

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (const next of units.slice(1)) {
    if (value < 1024) {
      break;
    }
    value /= 1024;
    unit = next;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${unit}`;
}

function formatDate(value?: string): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleString();
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export default function FilesPage({ config, onLogout, onConfigRefresh }: Props) {
  const { modal, message: messageApi } = App.useApp();
  const [bucket, setBucket] = useState("");
  const [prefix, setPrefix] = useState("");
  const [status, setStatus] = useState("active");
  const [sortBy, setSortBy] = useState<"name" | "created_at">("name");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<api.FilePage | null>(null);
  const [loading, setLoading] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [newBucketName, setNewBucketName] = useState("");
  const [creating, setCreating] = useState(false);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsForm, setSettingsForm] = useState<{
    default_bucket: string;
    presign_default_expires_seconds: number;
  } | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setPage(
        await api.listFiles({
          bucket: bucket || undefined,
          prefix: prefix || undefined,
          status: status || undefined,
          limit: PAGE_SIZE,
          offset,
          sortBy,
        }),
      );
    } catch (err) {
      messageApi.error(`加载失败：${errorText(err)}`);
    } finally {
      setLoading(false);
    }
  }, [bucket, prefix, status, offset, sortBy, messageApi]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const download = useCallback(
    async (file: api.FileInfo) => {
      try {
        const blob = await api.downloadFile(file.id);
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = file.original_filename || file.object_key.split("/").pop() || file.id;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      } catch (err) {
        messageApi.error(errorText(err));
      }
    },
    [messageApi],
  );

  const copyLink = useCallback(
    async (file: api.FileInfo) => {
      try {
        const { url } = await api.presignDownloadUrl(file.id);
        await navigator.clipboard.writeText(url);
        messageApi.success("下载链接已复制（15 分钟有效）");
      } catch (err) {
        messageApi.error(errorText(err));
      }
    },
    [messageApi],
  );

  const remove = useCallback(
    (file: api.FileInfo) => {
      modal.confirm({
        title: "确认删除",
        content: `确定删除 ${file.bucket}/${file.object_key}？`,
        okText: "删除",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: async () => {
          try {
            await api.deleteFile(file.id);
            messageApi.success("文件已删除");
            await reload();
          } catch (err) {
            messageApi.error(errorText(err));
          }
        },
      });
    },
    [modal, messageApi, reload],
  );

  const handleCreateBucket = useCallback(async () => {
    const name = newBucketName.trim();
    if (!name) {
      messageApi.warning("请输入存储桶名称");
      return;
    }
    setCreating(true);
    try {
      await api.createBucket(name);
      messageApi.success(`存储桶 ${name} 创建成功`);
      setCreateOpen(false);
      setNewBucketName("");
      await onConfigRefresh();
    } catch (err) {
      const code = errorText(err);
      if (code === "BUCKET_ALREADY_EXISTS") {
        messageApi.error(`存储桶 ${name} 已存在`);
      } else if (code === "INVALID_BUCKET_NAME") {
        messageApi.error("桶名不合法：3-63 位小写字母、数字、点、中划线");
      } else {
        messageApi.error(`创建失败：${code}`);
      }
    } finally {
      setCreating(false);
    }
  }, [newBucketName, messageApi, onConfigRefresh]);

  const openSettings = useCallback(async () => {
    setSettingsOpen(true);
    setSettingsLoading(true);
    try {
      const { storage } = await api.getSettings();
      setSettingsForm({
        default_bucket: storage.default_bucket,
        presign_default_expires_seconds: storage.presign_default_expires_seconds,
      });
    } catch (err) {
      messageApi.error(`加载设置失败：${errorText(err)}`);
    } finally {
      setSettingsLoading(false);
    }
  }, [messageApi]);

  const saveSettings = useCallback(async () => {
    if (!settingsForm) {
      return;
    }
    setSettingsSaving(true);
    try {
      await api.updateSettings(settingsForm);
      messageApi.success("设置已保存");
      setSettingsOpen(false);
      await onConfigRefresh();
    } catch (err) {
      messageApi.error(`保存失败：${errorText(err)}`);
    } finally {
      setSettingsSaving(false);
    }
  }, [settingsForm, messageApi, onConfigRefresh]);

  const columns: ColumnsType<api.FileInfo> = [
    {
      title: "对象",
      dataIndex: "object_key",
      ellipsis: true,
      render: (value: string, record) => (
        <span title={record.original_filename} style={{ fontFamily: "ui-monospace, monospace" }}>
          {value}
        </span>
      ),
    },
    { title: "Bucket", dataIndex: "bucket", width: 130 },
    {
      title: "大小",
      dataIndex: "size_bytes",
      width: 100,
      render: (value: number) => formatSize(value),
    },
    {
      title: "类型",
      dataIndex: "content_type",
      width: 180,
      ellipsis: true,
      render: (value?: string) => value ?? "—",
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (value: string) => (
        <Tag color={value === "deleted" ? "error" : "success"}>{value}</Tag>
      ),
    },
    {
      title: "过期时间",
      dataIndex: "expires_at",
      width: 160,
      render: (value?: string) => formatDate(value),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 160,
      render: (value?: string) => formatDate(value),
    },
    {
      title: "操作",
      key: "actions",
      width: 110,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title="下载">
            <Button
              size="small"
              type="text"
              icon={<Download size={16} />}
              onClick={() => void download(record)}
            />
          </Tooltip>
          <Tooltip title="复制下载链接">
            <Button
              size="small"
              type="text"
              icon={<Link2 size={16} />}
              onClick={() => void copyLink(record)}
            />
          </Tooltip>
          {record.status === "active" && (
            <Tooltip title="删除">
              <Button
                size="small"
                type="text"
                danger
                icon={<Trash2 size={16} />}
                onClick={() => remove(record)}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  const total = page?.total ?? 0;
  return (
    <div className="file-browse">
      <aside className={`file-nav${navCollapsed ? " collapsed" : ""}`}>
        <div className="file-nav-header">
          {!navCollapsed && <span>存储</span>}
          <Button
            type="text"
            size="small"
            icon={navCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
            onClick={() => setNavCollapsed((value) => !value)}
            aria-label={navCollapsed ? "展开导航" : "收起导航"}
          />
        </div>
        <div className="file-nav-body">
          <BucketTree
            config={config}
            bucket={bucket}
            prefix={prefix}
            onSelect={(nextBucket, nextPrefix) => {
              setBucket(nextBucket);
              setPrefix(nextPrefix);
              setOffset(0);
            }}
          />
        </div>
        <div className="file-nav-footer">
          <Tooltip title={navCollapsed ? "新建桶" : undefined} placement="right">
            <Button
              type="text"
              icon={<FolderPlus size={16} />}
              onClick={() => setCreateOpen(true)}
            >
              {!navCollapsed && "新建桶"}
            </Button>
          </Tooltip>
          <Tooltip title={navCollapsed ? "设置" : undefined} placement="right">
            <Button type="text" icon={<Settings size={16} />} onClick={() => void openSettings()}>
              {!navCollapsed && "设置"}
            </Button>
          </Tooltip>
          <Tooltip title={navCollapsed ? "退出登录" : undefined} placement="right">
            <Button type="text" icon={<LogOut size={16} />} onClick={onLogout}>
              {!navCollapsed && "退出"}
            </Button>
          </Tooltip>
        </div>
      </aside>
      <div className="file-browse-main">
        <h1>文件浏览</h1>
        <Space wrap style={{ marginBottom: 16 }}>
          <span>
            前缀：
            <Input
              value={prefix}
              onChange={(event) => {
                setPrefix(event.target.value);
                setOffset(0);
              }}
              placeholder="例如 reports/2026/"
              allowClear
              style={{ width: 220 }}
            />
          </span>
          <span>
            状态：
            <Select
              value={status}
              onChange={(value) => {
                setStatus(value);
                setOffset(0);
              }}
              options={[
                { value: "active", label: "正常" },
                { value: "deleted", label: "已删除" },
                { value: "", label: "全部" },
              ]}
              style={{ width: 110 }}
            />
          </span>
          <span>
            排序：
            <Select
              value={sortBy}
              onChange={(value) => {
                setSortBy(value);
                setOffset(0);
              }}
              options={[
                { value: "name", label: "按名称" },
                { value: "created_at", label: "按创建时间" },
              ]}
              style={{ width: 130 }}
            />
          </span>
        </Space>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={page?.items ?? []}
          loading={loading}
          locale={{ emptyText: "没有匹配的文件。" }}
          pagination={{
            current: Math.floor(offset / PAGE_SIZE) + 1,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            showTotal: (count) => `共 ${count} 个文件`,
            onChange: (nextPage) => setOffset((nextPage - 1) * PAGE_SIZE),
          }}
        />
      </div>

      <Modal
        title="新建存储桶"
        open={createOpen}
        onOk={() => void handleCreateBucket()}
        confirmLoading={creating}
        onCancel={() => {
          setCreateOpen(false);
          setNewBucketName("");
        }}
        okText="创建"
        cancelText="取消"
        destroyOnHidden
      >
        <Input
          value={newBucketName}
          onChange={(event) => setNewBucketName(event.target.value)}
          onPressEnter={() => void handleCreateBucket()}
          placeholder="例如 my-bucket"
          maxLength={63}
          autoFocus
        />
        <div className="form-hint">
          3-63 位：小写字母、数字、点、中划线；不能以点开头/结尾，不能包含连续的点。
        </div>
      </Modal>

      <Modal
        title="存储设置"
        open={settingsOpen}
        onOk={() => void saveSettings()}
        confirmLoading={settingsSaving}
        onCancel={() => setSettingsOpen(false)}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        {settingsLoading || !settingsForm ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin />
          </div>
        ) : (
          <div className="settings-form">
            <div className="settings-field">
              <label>默认存储桶</label>
              <Select
                value={settingsForm.default_bucket}
                onChange={(value) =>
                  setSettingsForm((form) => (form ? { ...form, default_bucket: value } : form))
                }
                options={config.uploads.allowed_buckets.map((name) => ({
                  value: name,
                  label: name,
                }))}
                style={{ width: "100%" }}
              />
              <div className="form-hint">上传等操作缺省使用的存储桶。</div>
            </div>
            <div className="settings-field">
              <label>下载链接默认有效期（秒）</label>
              <InputNumber
                min={60}
                max={config.presign.maximum_expires_seconds}
                value={settingsForm.presign_default_expires_seconds}
                onChange={(value) =>
                  setSettingsForm((form) =>
                    form
                      ? { ...form, presign_default_expires_seconds: value ?? 900 }
                      : form,
                  )
                }
                style={{ width: "100%" }}
              />
              <div className="form-hint">
                范围 60 - {config.presign.maximum_expires_seconds} 秒。
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
