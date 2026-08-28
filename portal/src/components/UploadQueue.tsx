import type { QueueFile } from "../upload/fileUpload";
import { downloadUrl } from "../api/client";
import { ProgressBar } from "./ProgressBar";

interface Props {
  items: QueueFile[];
  onPause: (item: QueueFile) => void;
  onResume: (item: QueueFile) => void;
  onReselect: (item: QueueFile) => void;
  onCancel: (item: QueueFile) => void;
  onRetry: (item: QueueFile) => void;
}

const STATUS_LABEL: Record<QueueFile["status"], string> = {
  pending: "等待中",
  uploading: "上传中",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
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
            <span className={`badge badge-${item.status}`}>{STATUS_LABEL[item.status]}</span>
          </div>
          <div className="queue-meta">
            {item.objectKey} · {(item.size / 1024 / 1024).toFixed(2)} MB
            {item.error ? <span className="error-text"> · {item.error}</span> : null}
          </div>
          <ProgressBar value={item.progress} />
          <div className="queue-actions">
            {item.status === "uploading" && (
              <button onClick={() => onPause(item)}>暂停</button>
            )}
            {item.status === "paused" && (
              <button onClick={() => onResume(item)}>继续</button>
            )}
            {item.needsFile && (
              <button onClick={() => onReselect(item)}>重新选择</button>
            )}
            {item.status === "failed" && (
              <button onClick={() => onRetry(item)}>重试</button>
            )}
            {(item.status === "paused" || item.status === "failed") && (
              <button onClick={() => onCancel(item)}>取消</button>
            )}
            {item.status === "completed" && item.fileId && (
              <a href={downloadUrl(item.fileId)} target="_blank" rel="noreferrer">
                下载
              </a>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
