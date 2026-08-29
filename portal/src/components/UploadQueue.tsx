import { Button, Progress, Space, Tag } from "antd";
import { Download, FolderOpen, Pause, Play, RotateCw, X } from "lucide-react";
import type { QueueFile } from "../upload/fileUpload";
import { downloadUrl } from "../api/client";
import { useI18n } from "../i18n";

interface Props {
  items: QueueFile[];
  onPause: (item: QueueFile) => void;
  onResume: (item: QueueFile) => void;
  onReselect: (item: QueueFile) => void;
  onCancel: (item: QueueFile) => void;
  onRetry: (item: QueueFile) => void;
}

const STATUS_KEY: Record<QueueFile["status"], { key: string; color: string }> = {
  pending: { key: "queue.pending", color: "default" },
  uploading: { key: "queue.uploading", color: "processing" },
  paused: { key: "queue.paused", color: "warning" },
  completed: { key: "queue.completed", color: "success" },
  failed: { key: "queue.failed", color: "error" },
};

export function UploadQueue({ items, onPause, onResume, onReselect, onCancel, onRetry }: Props) {
  const { t } = useI18n();
  if (items.length === 0) {
    return <p className="empty">{t("queue.empty")}</p>;
  }
  return (
    <ul className="queue">
      {items.map((item) => (
        <li key={item.id} className={`queue-item ${item.status}`}>
          <div className="queue-main">
            <span className="queue-name" title={item.objectKey}>
              {item.name}
            </span>
            <Tag color={STATUS_KEY[item.status].color}>{t(STATUS_KEY[item.status].key)}</Tag>
          </div>
          <div className="queue-meta">
            {item.objectKey} · {(item.size / 1024 / 1024).toFixed(2)} MB
            {item.error ? <span className="error-text"> · {item.error}</span> : null}
          </div>
          <Progress percent={Math.round(item.progress * 100)} size="small" status={item.status === "failed" ? "exception" : undefined} />
          <Space wrap style={{ marginTop: 10 }}>
            {item.status === "uploading" && (
              <Button size="small" icon={<Pause size={14} />} onClick={() => onPause(item)}>
                暂停
              </Button>
            )}
            {item.status === "paused" && (
              <Button size="small" icon={<Play size={14} />} onClick={() => onResume(item)}>
                继续
              </Button>
            )}
            {item.needsFile && (
              <Button size="small" icon={<FolderOpen size={14} />} onClick={() => onReselect(item)}>
                重新选择
              </Button>
            )}
            {item.status === "failed" && (
              <Button size="small" icon={<RotateCw size={14} />} onClick={() => onRetry(item)}>
                重试
              </Button>
            )}
            {(item.status === "paused" || item.status === "failed") && (
              <Button size="small" icon={<X size={14} />} onClick={() => onCancel(item)}>
                取消
              </Button>
            )}
            {item.status === "completed" && item.fileId && (
              <Button size="small" icon={<Download size={14} />} href={downloadUrl(item.fileId)} target="_blank">
                下载
              </Button>
            )}
          </Space>
        </li>
      ))}
    </ul>
  );
}
