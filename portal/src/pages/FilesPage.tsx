import { useCallback, useEffect, useState } from "react";
import {
  App,
  Button,
  Descriptions,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
} from "antd";
import {
  Download,
  FolderPlus,
  Languages,
  Link2,
  LogOut,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sun,
  Trash2,
} from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import * as api from "../api/client";
import { BucketTree } from "../components/BucketTree";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";

interface Props {
  config: api.ClientConfig;
  onLogout: () => void;
  onConfigRefresh: () => Promise<void>;
}

const PAGE_SIZE = 50;

interface SettingsForm {
  storage: {
    default_bucket: string;
    presign_default_expires_seconds: number;
  };
  uploads: {
    maximum_file_size_bytes: number;
    direct_upload_threshold_bytes: number;
    default_mode: string;
    multipart: { default_part_size_bytes: number };
    session: { expires_after_seconds: number };
  };
  lifecycle: { default_policy: { mode: string; action: string; ttl_seconds: number } };
}

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
  const { t, lang, setLang } = useI18n();
  const { mode, toggle: toggleTheme } = useTheme();

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
  const [settings, setSettings] = useState<api.RuntimeSettings | null>(null);
  const [settingsForm, setSettingsForm] = useState<SettingsForm | null>(null);

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
      messageApi.error(t("files.loadFailed", { msg: errorText(err) }));
    } finally {
      setLoading(false);
    }
  }, [bucket, prefix, status, offset, sortBy, messageApi, t]);

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
        messageApi.success(t("files.linkCopied"));
      } catch (err) {
        messageApi.error(errorText(err));
      }
    },
    [messageApi, t],
  );

  const remove = useCallback(
    (file: api.FileInfo) => {
      modal.confirm({
        title: t("files.deleteTitle"),
        content: t("files.deleteContent", { path: `${file.bucket}/${file.object_key}` }),
        okText: t("common.delete"),
        okButtonProps: { danger: true },
        cancelText: t("common.cancel"),
        onOk: async () => {
          try {
            await api.deleteFile(file.id);
            messageApi.success(t("files.deleted"));
            await reload();
          } catch (err) {
            messageApi.error(t("files.deleteFailed", { msg: errorText(err) }));
          }
        },
      });
    },
    [modal, messageApi, reload, t],
  );

  const handleCreateBucket = useCallback(async () => {
    const name = newBucketName.trim();
    if (!name) {
      messageApi.warning(t("bucket.required"));
      return;
    }
    setCreating(true);
    try {
      await api.createBucket(name);
      messageApi.success(t("bucket.created", { name }));
      setCreateOpen(false);
      setNewBucketName("");
      await onConfigRefresh();
    } catch (err) {
      const code = errorText(err);
      if (code === "BUCKET_ALREADY_EXISTS") {
        messageApi.error(t("bucket.exists", { name }));
      } else if (code === "INVALID_BUCKET_NAME") {
        messageApi.error(t("bucket.invalidName"));
      } else {
        messageApi.error(t("bucket.createFailed", { msg: code }));
      }
    } finally {
      setCreating(false);
    }
  }, [newBucketName, messageApi, onConfigRefresh, t]);

  const openSettings = useCallback(async () => {
    setSettingsOpen(true);
    setSettingsLoading(true);
    try {
      const data = await api.getSettings();
      setSettings(data);
      setSettingsForm({
        storage: {
          default_bucket: data.storage.default_bucket,
          presign_default_expires_seconds: data.storage.presign_default_expires_seconds,
        },
        uploads: {
          maximum_file_size_bytes: data.uploads.maximum_file_size_bytes,
          direct_upload_threshold_bytes: data.uploads.direct_upload_threshold_bytes,
          default_mode: data.uploads.default_mode,
          multipart: { default_part_size_bytes: data.uploads.multipart.default_part_size_bytes },
          session: { expires_after_seconds: data.uploads.session.expires_after_seconds },
        },
        lifecycle: { default_policy: { ...data.lifecycle.default_policy } },
      });
    } catch (err) {
      messageApi.error(t("settings.loadFailed", { msg: errorText(err) }));
    } finally {
      setSettingsLoading(false);
    }
  }, [messageApi, t]);

  const saveSettings = useCallback(async () => {
    if (!settingsForm) {
      return;
    }
    setSettingsSaving(true);
    try {
      await api.updateSettings({
        storage: settingsForm.storage,
        uploads: settingsForm.uploads,
        lifecycle: settingsForm.lifecycle,
      });
      messageApi.success(t("settings.saved"));
      setSettingsOpen(false);
      await onConfigRefresh();
    } catch (err) {
      messageApi.error(t("settings.saveFailed", { msg: errorText(err) }));
    } finally {
      setSettingsSaving(false);
    }
  }, [settingsForm, messageApi, onConfigRefresh, t]);

  const columns: ColumnsType<api.FileInfo> = [
    {
      title: t("files.colObject"),
      dataIndex: "object_key",
      ellipsis: true,
      render: (value: string, record) => (
        <span title={record.original_filename} style={{ fontFamily: "ui-monospace, monospace" }}>
          {value}
        </span>
      ),
    },
    { title: t("files.colBucket"), dataIndex: "bucket", width: 130 },
    {
      title: t("files.colSize"),
      dataIndex: "size_bytes",
      width: 100,
      render: (value: number) => formatSize(value),
    },
    {
      title: t("files.colType"),
      dataIndex: "content_type",
      width: 180,
      ellipsis: true,
      render: (value?: string) => value ?? "—",
    },
    {
      title: t("files.colStatus"),
      dataIndex: "status",
      width: 90,
      render: (value: string) => (
        <Tag color={value === "deleted" ? "error" : "success"}>{value}</Tag>
      ),
    },
    {
      title: t("files.colExpires"),
      dataIndex: "expires_at",
      width: 160,
      render: (value?: string) => formatDate(value),
    },
    {
      title: t("files.colCreated"),
      dataIndex: "created_at",
      width: 160,
      render: (value?: string) => formatDate(value),
    },
    {
      title: t("files.colActions"),
      key: "actions",
      width: 110,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title={t("common.download")}>
            <Button
              size="small"
              type="text"
              icon={<Download size={16} />}
              onClick={() => void download(record)}
            />
          </Tooltip>
          <Tooltip title={t("common.copyLink")}>
            <Button
              size="small"
              type="text"
              icon={<Link2 size={16} />}
              onClick={() => void copyLink(record)}
            />
          </Tooltip>
          {record.status === "active" && (
            <Tooltip title={t("common.delete")}>
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

  const switchLang = useCallback(() => {
    setLang(lang === "zh" ? "en" : "zh");
  }, [lang, setLang]);

  const storageInfo = settings?.storage.info;
  const total = page?.total ?? 0;
  return (
    <div className="file-browse">
      <aside className={`file-nav${navCollapsed ? " collapsed" : ""}`}>
        <div className="file-nav-header">
          {!navCollapsed && <span className="file-nav-title">{t("nav.storage")}</span>}
          <Tooltip title={navCollapsed ? t("sidebar.createBucket") : undefined} placement="right">
            <Button
              type="text"
              size="small"
              icon={<FolderPlus size={16} />}
              onClick={() => setCreateOpen(true)}
              className="file-nav-create"
              aria-label={t("sidebar.createBucket")}
            >
              {!navCollapsed && t("sidebar.createBucket")}
            </Button>
          </Tooltip>
          <Button
            type="text"
            size="small"
            icon={navCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
            onClick={() => setNavCollapsed((value) => !value)}
            aria-label={navCollapsed ? t("nav.expand") : t("nav.collapse")}
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
          <Tooltip title={navCollapsed ? t("sidebar.settings") : undefined} placement="right">
            <Button type="text" icon={<Settings size={16} />} onClick={() => void openSettings()}>
              {!navCollapsed && t("sidebar.settings")}
            </Button>
          </Tooltip>
          <Tooltip title={navCollapsed ? t("sidebar.language") : undefined} placement="right">
            <Button type="text" icon={<Languages size={16} />} onClick={switchLang}>
              {!navCollapsed && (lang === "zh" ? "EN" : "中文")}
            </Button>
          </Tooltip>
          <Tooltip title={navCollapsed ? t("sidebar.theme") : undefined} placement="right">
            <Button
              type="text"
              icon={mode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
              onClick={toggleTheme}
            >
              {!navCollapsed && (mode === "dark" ? t("sidebar.theme") + " · ☀" : t("sidebar.theme") + " · ☾")}
            </Button>
          </Tooltip>
          <Tooltip title={navCollapsed ? t("sidebar.logoutTip") : undefined} placement="right">
            <Button type="text" icon={<LogOut size={16} />} onClick={onLogout}>
              {!navCollapsed && t("sidebar.logout")}
            </Button>
          </Tooltip>
        </div>
      </aside>
      <div className="file-browse-main">
        <h1>{t("files.title")}</h1>
        <Space wrap style={{ marginBottom: 16 }}>
          <span>
            {t("files.prefix")}
            <Input
              value={prefix}
              onChange={(event) => {
                setPrefix(event.target.value);
                setOffset(0);
              }}
              placeholder="reports/2026/"
              allowClear
              style={{ width: 220 }}
            />
          </span>
          <span>
            {t("files.status")}
            <Select
              value={status}
              onChange={(value) => {
                setStatus(value);
                setOffset(0);
              }}
              options={[
                { value: "active", label: t("files.statusActive") },
                { value: "deleted", label: t("files.statusDeleted") },
                { value: "", label: t("files.statusAll") },
              ]}
              style={{ width: 110 }}
            />
          </span>
          <span>
            {t("files.sort")}
            <Select
              value={sortBy}
              onChange={(value) => {
                setSortBy(value);
                setOffset(0);
              }}
              options={[
                { value: "name", label: t("files.sortName") },
                { value: "created_at", label: t("files.sortCreated") },
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
          locale={{ emptyText: t("files.empty") }}
          pagination={{
            current: Math.floor(offset / PAGE_SIZE) + 1,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            showTotal: (count) => t("files.total", { count }),
            onChange: (nextPage) => setOffset((nextPage - 1) * PAGE_SIZE),
          }}
        />
      </div>

      <Modal
        title={t("bucket.createTitle")}
        open={createOpen}
        onOk={() => void handleCreateBucket()}
        confirmLoading={creating}
        onCancel={() => {
          setCreateOpen(false);
          setNewBucketName("");
        }}
        okText={t("common.create")}
        cancelText={t("common.cancel")}
        destroyOnHidden
      >
        <Input
          value={newBucketName}
          onChange={(event) => setNewBucketName(event.target.value)}
          onPressEnter={() => void handleCreateBucket()}
          placeholder={t("bucket.placeholder")}
          maxLength={63}
          autoFocus
        />
        <div className="form-hint">{t("bucket.hint")}</div>
      </Modal>

      <Modal
        title={t("settings.title")}
        open={settingsOpen}
        onOk={() => void saveSettings()}
        confirmLoading={settingsSaving}
        onCancel={() => setSettingsOpen(false)}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        destroyOnHidden
        width={620}
      >
        {settingsLoading || !settingsForm || !settings ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin />
          </div>
        ) : (
          <Tabs
            items={[
              {
                key: "storage",
                label: t("settings.storage"),
                children: (
                  <div className="settings-form">
                    <div className="settings-field">
                      <label>{t("settings.defaultBucket")}</label>
                      <Select
                        value={settingsForm.storage.default_bucket}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  storage: { ...form.storage, default_bucket: value },
                                }
                              : form,
                          )
                        }
                        options={(storageInfo?.allowed_buckets ?? config.uploads.allowed_buckets).map(
                          (name) => ({ value: name, label: name }),
                        )}
                        style={{ width: "100%" }}
                      />
                      <div className="form-hint">{t("settings.defaultBucketHint")}</div>
                    </div>
                    <div className="settings-field">
                      <label>{t("settings.presignExpiry")}</label>
                      <InputNumber
                        min={60}
                        max={settings.storage.maximum_expires_seconds}
                        value={settingsForm.storage.presign_default_expires_seconds}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  storage: {
                                    ...form.storage,
                                    presign_default_expires_seconds: value ?? 900,
                                  },
                                }
                              : form,
                          )
                        }
                        style={{ width: "100%" }}
                      />
                      <div className="form-hint">
                        {t("settings.presignRange", {
                          min: 60,
                          max: settings.storage.maximum_expires_seconds,
                        })}
                      </div>
                    </div>
                    <div className="settings-divider" />
                    <div className="settings-field">
                      <label>{t("settings.backendInfo")}</label>
                      {storageInfo && (
                        <Descriptions size="small" column={1} bordered>
                          <Descriptions.Item label={t("settings.backend")}>
                            {storageInfo.backend}
                          </Descriptions.Item>
                          {storageInfo.root_path && (
                            <Descriptions.Item label={t("settings.rootPath")}>
                              {storageInfo.root_path}
                            </Descriptions.Item>
                          )}
                          {storageInfo.endpoint && (
                            <Descriptions.Item label={t("settings.endpoint")}>
                              {storageInfo.endpoint}
                            </Descriptions.Item>
                          )}
                          {storageInfo.region && (
                            <Descriptions.Item label={t("settings.region")}>
                              {storageInfo.region}
                            </Descriptions.Item>
                          )}
                          {storageInfo.access_key_configured !== undefined && (
                            <Descriptions.Item label={t("settings.accessKeyConfigured")}>
                              {storageInfo.access_key_configured ? "✓" : "—"}
                            </Descriptions.Item>
                          )}
                          {storageInfo.force_path_style !== undefined && (
                            <Descriptions.Item label={t("settings.forcePathStyle")}>
                              {String(storageInfo.force_path_style)}
                            </Descriptions.Item>
                          )}
                          <Descriptions.Item label={t("settings.allowedBuckets")}>
                            {storageInfo.allowed_buckets.join(", ")}
                          </Descriptions.Item>
                          <Descriptions.Item label={t("settings.capabilities")}>
                            {Object.entries(storageInfo.capabilities)
                              .filter(([, enabled]) => enabled)
                              .map(([name]) => name)
                              .join(", ") || "—"}
                          </Descriptions.Item>
                        </Descriptions>
                      )}
                      <div className="form-hint">{t("settings.storageHint")}</div>
                    </div>
                  </div>
                ),
              },
              {
                key: "uploads",
                label: t("settings.uploads"),
                children: (
                  <div className="settings-form">
                    <div className="settings-field">
                      <label>{t("settings.maxFileSize")}</label>
                      <InputNumber
                        min={1}
                        value={settingsForm.uploads.maximum_file_size_bytes}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  uploads: { ...form.uploads, maximum_file_size_bytes: value ?? 0 },
                                }
                              : form,
                          )
                        }
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div className="settings-field">
                      <label>{t("settings.directThreshold")}</label>
                      <InputNumber
                        min={0}
                        value={settingsForm.uploads.direct_upload_threshold_bytes}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  uploads: {
                                    ...form.uploads,
                                    direct_upload_threshold_bytes: value ?? 0,
                                  },
                                }
                              : form,
                          )
                        }
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div className="settings-field">
                      <label>{t("settings.defaultMode")}</label>
                      <Select
                        value={settingsForm.uploads.default_mode}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? { ...form, uploads: { ...form.uploads, default_mode: value } }
                              : form,
                          )
                        }
                        options={[
                          { value: "automatic", label: t("settings.modeAutomatic") },
                          { value: "proxy", label: t("settings.modeProxy") },
                          { value: "presigned", label: t("settings.modePresigned") },
                        ]}
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div className="settings-field">
                      <label>{t("settings.defaultPartSize")}</label>
                      <InputNumber
                        min={settings.uploads.multipart.minimum_part_size_bytes}
                        max={settings.uploads.multipart.maximum_part_size_bytes}
                        value={settingsForm.uploads.multipart.default_part_size_bytes}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  uploads: {
                                    ...form.uploads,
                                    multipart: {
                                      ...form.uploads.multipart,
                                      default_part_size_bytes: value ?? 0,
                                    },
                                  },
                                }
                              : form,
                          )
                        }
                        style={{ width: "100%" }}
                      />
                      <div className="form-hint">
                        {settings.uploads.multipart.minimum_part_size_bytes} -{" "}
                        {settings.uploads.multipart.maximum_part_size_bytes}
                      </div>
                    </div>
                    <div className="settings-field">
                      <label>{t("settings.sessionExpiry")}</label>
                      <InputNumber
                        min={60}
                        max={settings.uploads.session.maximum_lifetime_seconds}
                        value={settingsForm.uploads.session.expires_after_seconds}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  uploads: {
                                    ...form.uploads,
                                    session: {
                                      ...form.uploads.session,
                                      expires_after_seconds: value ?? 60,
                                    },
                                  },
                                }
                              : form,
                          )
                        }
                        style={{ width: "100%" }}
                      />
                    </div>
                  </div>
                ),
              },
              {
                key: "lifecycle",
                label: t("settings.lifecycle"),
                children: (
                  <div className="settings-form">
                    <div className="settings-field">
                      <label>{t("settings.lifecycleMode")}</label>
                      <Select
                        value={settingsForm.lifecycle.default_policy.mode}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  lifecycle: {
                                    default_policy: { ...form.lifecycle.default_policy, mode: value },
                                  },
                                }
                              : form,
                          )
                        }
                        options={settings.lifecycle.allowed_modes.map((mode) => ({
                          value: mode,
                          label: mode,
                        }))}
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div className="settings-field">
                      <label>{t("settings.lifecycleAction")}</label>
                      <Select
                        value={settingsForm.lifecycle.default_policy.action}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  lifecycle: {
                                    default_policy: {
                                      ...form.lifecycle.default_policy,
                                      action: value,
                                    },
                                  },
                                }
                              : form,
                          )
                        }
                        options={settings.lifecycle.allowed_actions.map((action) => ({
                          value: action,
                          label: action,
                        }))}
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div className="settings-field">
                      <label>{t("settings.lifecycleTtl")}</label>
                      <InputNumber
                        min={settings.lifecycle.minimum_ttl_seconds}
                        max={settings.lifecycle.maximum_ttl_seconds}
                        value={settingsForm.lifecycle.default_policy.ttl_seconds}
                        onChange={(value) =>
                          setSettingsForm((form) =>
                            form
                              ? {
                                  ...form,
                                  lifecycle: {
                                    default_policy: {
                                      ...form.lifecycle.default_policy,
                                      ttl_seconds: value ?? settings.lifecycle.minimum_ttl_seconds,
                                    },
                                  },
                                }
                              : form,
                          )
                        }
                        style={{ width: "100%" }}
                      />
                      <div className="form-hint">
                        {settings.lifecycle.minimum_ttl_seconds} - {settings.lifecycle.maximum_ttl_seconds}
                      </div>
                    </div>
                  </div>
                ),
              },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}
