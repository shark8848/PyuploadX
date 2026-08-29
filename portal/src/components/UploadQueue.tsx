import { Button, Progress, Space, Tag } from "antd";
import { DownloadOutlined, PauseOutlined, CaretRightOutlined, FolderOpenOutlined, CloseOutlined, ReloadOutlined } from "@ant-design/icons";
import type { QueueFile } from "../upload/fileUpload";
import { downloadUrl } from "../api/client";

interface Props {
  items: QueueFile[];
  onPause: (item: QueueFile) => void;
  onResume: (item: QueueFile) => void;
  onReselect: (item: QueueFile) => void;
  onCancel: (item: QueueFile) => void;
  onRetry: (item: QueueFile) => void;
}

const STATUS_TAG: Record<QueueFile["status"], { label: string; color: string }> = {
  pending: { label: "等待中", color: "default" },
  uploading: { label: "上传中", color: "processing" },
  paused: { label: "已暂停", color: "warning" },
  completed: { label: "已完成", color: "success" },
  failed: { label: "失败", color: "error" },
};

export function UploadQueue({ items, onPause, onResume, onReselect, onCancel, onRetry }: Props) {
  if (items.length === 0) {
    return <p className="empty">暂无上传任务</p>;
  }
  return (
    <ul className="queue">
      {items.map((item) => (
        <li key={item.id} className={`queue-item ${item.status}`}>
          <div className="queue-main">
            <span className="queue-name" title={item.objectKey}>
              {item.name}
            </span>
            <Tag color={STATUS_TAG[item.status].color}>{STATUS_TAG[item.status].label}</Tag>
          </div>
          <div className="queue-meta">
            {item.objectKey} · {(item.size / 1024 / 1024).toFixed(2)} MB
            {item.error ? <span className="error-text"> · {item.error}</span> : null}
          </div>
          <Progress percent={Math.round(item.progress * 100)} size="small" status={item.status === "failed" ? "exception" : undefined} />
          <Space wrap style={{ marginTop: 10 }}>
            {item.status === "uploading" && (
              <Button size="small" icon={<PauseOutlined />} onClick={() => onPause(item)}>
                暂停
              </Button>
            )}
            {item.status === "paused" && (
              <Button size="small" icon={<CaretRightOutlined />} onClick={() => onResume(item)}>
                继续
              </Button>
            )}
            {item.needsFile && (
              <Button size="small" icon={<FolderOpenOutlined />} onClick={() => onReselect(item)}>
                重新选择
              </Button>
            )}
            {item.status === "failed" && (
              <Button size="small" icon={<ReloadOutlined />} onClick={() => onRetry(item)}>
                重试
              </Button>
            )}
            {(item.status === "paused" || item.status === "failed") && (
              <Button size="small" icon={<CloseOutlined />} onClick={() => onCancel(item)}>
                取消
              </Button>
            )}
            {item.status === "completed" && item.fileId && (
              <Button size="small" icon={<DownloadOutlined />} href={downloadUrl(item.fileId)} target="_blank">
                下载
              </Button>
            )}
          </Space>
        </li>
      ))}
    </ul>
  );
}
