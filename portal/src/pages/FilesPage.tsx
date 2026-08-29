import { useCallback, useEffect, useState, type Key } from "react";
import { App, Button, Input, Select, Space, Table, Tag, Tooltip } from "antd";
import { Download, Link2, Trash2 } from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import * as api from "../api/client";
import { useI18n } from "../i18n";

interface Props {
  bucket: string;
  prefix: string;
  onPrefixChange: (prefix: string) => void;
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

export default function FilesPage({
  bucket,
  prefix,
  onPrefixChange,
}: Props) {
  const { modal, message: messageApi } = App.useApp();
  const { t } = useI18n();

  const [status, setStatus] = useState("active");
  const [sortBy, setSortBy] = useState<"name" | "created_at">("name");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<api.FilePage | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<Key[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<api.FileInfo[]>([]);

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

  const downloadMany = useCallback(async () => {
    if (selectedFiles.length === 0) {
      return;
    }
    try {
      for (const file of selectedFiles) {
        const blob = await api.downloadFile(file.id);
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = file.original_filename || file.object_key.split("/").pop() || file.id;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      messageApi.error(errorText(err));
    }
  }, [selectedFiles, messageApi]);

  const removeMany = useCallback(() => {
    if (selectedFiles.length === 0) {
      return;
    }
    const files = selectedFiles;
    modal.confirm({
      title: t("files.batchDeleteTitle"),
      content: t("files.batchDeleteContent", { count: files.length }),
      okText: t("common.delete"),
      okButtonProps: { danger: true },
      cancelText: t("common.cancel"),
      onOk: async () => {
        try {
          for (const file of files) {
            await api.deleteFile(file.id);
          }
          messageApi.success(t("files.deletedMany", { count: files.length }));
          setSelectedKeys([]);
          setSelectedFiles([]);
          await reload();
        } catch (err) {
          messageApi.error(t("files.deleteFailed", { msg: errorText(err) }));
        }
      },
    });
  }, [modal, messageApi, reload, t, selectedFiles]);

  const rowSelection = {
    selectedRowKeys: selectedKeys,
    onChange: (keys: Key[], rows: api.FileInfo[]) => {
      setSelectedKeys(keys);
      setSelectedFiles((prev) => {
        const byId = new Map(prev.map((file) => [file.id, file]));
        for (const row of rows) {
          byId.set(row.id, row);
        }
        return [...byId.values()].filter((file) => keys.includes(file.id));
      });
    },
    getCheckboxProps: (record: api.FileInfo) => ({
      disabled: record.status === "deleted",
    }),
  };

  const columns: ColumnsType<api.FileInfo> = [
    {
      title: t("files.colObject"),
      dataIndex: "object_key",
      width: 240,
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

  const total = page?.total ?? 0;
  return (
    <>
      <h1>{t("files.title")}</h1>
      <Space wrap style={{ marginBottom: 16 }}>
        <span>
          {t("files.prefix")}
          <Input
            value={prefix}
            onChange={(event) => {
              onPrefixChange(event.target.value);
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
      {selectedKeys.length > 0 && (
        <Space wrap style={{ marginBottom: 12 }} size={8}>
          <span className="file-selected-count">
            {t("files.selected", { count: selectedKeys.length })}
          </span>
          <Button
            size="small"
            type="primary"
            ghost
            icon={<Download size={16} />}
            onClick={() => void downloadMany()}
          >
            {t("files.batchDownload")}
          </Button>
          <Button size="small" danger icon={<Trash2 size={16} />} onClick={removeMany}>
            {t("files.batchDelete")}
          </Button>
        </Space>
      )}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={page?.items ?? []}
        loading={loading}
        scroll={{ x: "max-content" }}
        rowSelection={rowSelection}
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
    </>
  );
}
