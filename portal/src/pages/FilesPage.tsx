import { useCallback, useEffect, useState } from "react";
import { App, Button, Input, Select, Space, Table, Tag } from "antd";
import { CopyOutlined, DeleteOutlined, DownloadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import * as api from "../api/client";

interface Props {
  config: api.ClientConfig;
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

export default function FilesPage({ config }: Props) {
  const { modal, message: messageApi } = App.useApp();
  const [bucket, setBucket] = useState("");
  const [prefix, setPrefix] = useState("");
  const [status, setStatus] = useState("active");
  const [sortBy, setSortBy] = useState<"name" | "created_at">("name");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<api.FilePage | null>(null);
  const [loading, setLoading] = useState(false);

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
      messageApi.error(`加载失败：${err instanceof Error ? err.message : String(err)}`);
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
        messageApi.error(err instanceof Error ? err.message : String(err));
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
        messageApi.error(err instanceof Error ? err.message : String(err));
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
            messageApi.error(err instanceof Error ? err.message : String(err));
          }
        },
      });
    },
    [modal, messageApi, reload],
  );

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
      width: 200,
      render: (_, record) => (
        <Space size={4}>
          <Button size="small" icon={<DownloadOutlined />} onClick={() => void download(record)}>
            下载
          </Button>
          <Button size="small" icon={<CopyOutlined />} onClick={() => void copyLink(record)}>
            复制链接
          </Button>
          {record.status === "active" && (
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => remove(record)}
            />
          )}
        </Space>
      ),
    },
  ];

  const total = page?.total ?? 0;
  return (
    <div className="page">
      <h1>文件浏览</h1>
      <Space wrap style={{ margin: "16px 0" }}>
        <span>
          Bucket：
          <Select
            value={bucket}
            onChange={(value) => { setBucket(value); setOffset(0); }}
            options={[{ value: "", label: "全部" }, ...config.uploads.allowed_buckets.map((name) => ({ value: name, label: name }))]}
            style={{ width: 140 }}
          />
        </span>
        <span>
          前缀：
          <Input
            value={prefix}
            onChange={(event) => { setPrefix(event.target.value); setOffset(0); }}
            placeholder="例如 reports/2026/"
            allowClear
            style={{ width: 200 }}
          />
        </span>
        <span>
          状态：
          <Select
            value={status}
            onChange={(value) => { setStatus(value); setOffset(0); }}
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
            onChange={(value) => { setSortBy(value); setOffset(0); }}
            options={[
              { value: "name", label: "按名称" },
              { value: "created_at", label: "按创建时间" },
            ]}
            style={{ width: 130 }}
          />
        </span>
      </Space>
      <Table<api.FileInfo>
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
          onChange: (current) => setOffset((current - 1) * PAGE_SIZE),
        }}
      />
    </div>
  );
}
