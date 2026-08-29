import { useState } from "react";
import { Button, Progress, Space, Tag } from "antd";
import { ChevronDown, ChevronUp, Download, FolderOpen, Pause, Play, RotateCw, Trash2, X } from "lucide-react";
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
  onClearCompleted: () => void;
}

const DEFAULT_VISIBLE_COMPLETED = 20;

const STATUS_KEY: Record<QueueFile["status"], { key: string; color: string }> = {
  pending: { key: "queue.pending", color: "default" },
  uploading: { key: "queue.uploading", color: "processing" },
  paused: { key: "queue.paused", color: "warning" },
  completed: { key: "queue.completed", color: "success" },
  failed: { key: "queue.failed", color: "error" },
};

function QueueItem({
  item,
  onPause,
  onResume,
  onReselect,
  onCancel,
  onRetry,
}: Omit<Props, "items" | "onClearCompleted"> & { item: QueueFile }) {
  const { t } = useI18n();
  return (
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
      <Progress
        percent={Math.round(item.progress * 100)}
        size="small"
        status={item.status === "failed" ? "exception" : undefined}
      />
      <Space wrap style={{ marginTop: 10 }}>
        {item.status === "uploading" && (
          <Button size="small" icon={<Pause size={14} />} onClick={() => onPause(item)}>
            {t("queue.pause")}
          </Button>
        )}
        {item.status === "paused" && (
          <Button size="small" icon={<Play size={14} />} onClick={() => onResume(item)}>
            {t("queue.resume")}
          </Button>
        )}
        {item.needsFile && (
          <Button size="small" icon={<FolderOpen size={14} />} onClick={() => onReselect(item)}>
            {t("queue.reselect")}
          </Button>
        )}
        {item.status === "failed" && (
          <Button size="small" icon={<RotateCw size={14} />} onClick={() => onRetry(item)}>
            {t("queue.retry")}
          </Button>
        )}
        {(item.status === "paused" || item.status === "failed") && (
          <Button size="small" icon={<X size={14} />} onClick={() => onCancel(item)}>
            {t("queue.cancel")}
          </Button>
        )}
        {item.status === "completed" && item.fileId && (
          <Button
            size="small"
            icon={<Download size={14} />}
            href={downloadUrl(item.fileId)}
            target="_blank"
          >
            {t("queue.download")}
          </Button>
        )}
      </Space>
    </li>
  );
}

export function UploadQueue({
  items,
  onPause,
  onResume,
  onReselect,
  onCancel,
  onRetry,
  onClearCompleted,
}: Props) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const active = items.filter((item) => item.status !== "completed");
  const done = items.filter((item) => item.status === "completed");
  const visibleDone = expanded ? done : done.slice(0, DEFAULT_VISIBLE_COMPLETED);

  if (items.length === 0) {
    return <p className="empty">{t("queue.empty")}</p>;
  }

  return (
    <>
      {active.length > 0 && (
        <ul className="queue">
          {active.map((item) => (
            <QueueItem
              key={item.id}
              item={item}
              onPause={onPause}
              onResume={onResume}
              onReselect={onReselect}
              onCancel={onCancel}
              onRetry={onRetry}
            />
          ))}
        </ul>
      )}
      {done.length > 0 && (
        <div className="queue-history">
          <div className="queue-history-head">
            <span className="queue-history-title">
              {t("queue.history")} ({done.length})
            </span>
            <Space size={4}>
              <Button
                size="small"
                type="text"
                icon={expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                onClick={() => setExpanded((value) => !value)}
              >
                {expanded ? t("queue.showLess") : t("queue.showAll", { count: done.length })}
              </Button>
              <Button size="small" type="text" icon={<Trash2 size={14} />} onClick={onClearCompleted}>
                {t("queue.clearCompleted")}
              </Button>
            </Space>
          </div>
          <ul className="queue">
            {visibleDone.map((item) => (
              <QueueItem
                key={item.id}
                item={item}
                onPause={onPause}
                onResume={onResume}
                onReselect={onReselect}
                onCancel={onCancel}
                onRetry={onRetry}
              />
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
