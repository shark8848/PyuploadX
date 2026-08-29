import { useCallback, useEffect, useRef, useState } from "react";
import { App, Input, Select, Space } from "antd";
import * as api from "../api/client";
import { useI18n } from "../i18n";
import { FileDrop } from "../components/FileDrop";
import { LifecycleSelect } from "../components/LifecycleSelect";
import { UploadQueue } from "../components/UploadQueue";
import {
  cancelUpload,
  clearCompleted,
  loadQueued,
  pauseUpload,
  persist,
  pruneCompletedHistory,
  uploadQueuedFile,
  type QueueFile,
} from "../upload/fileUpload";

interface Props {
  config: api.ClientConfig;
}

function defaultLifecycle(config: api.ClientConfig): string | undefined {
  if (!config.lifecycle.enabled) {
    return undefined;
  }
  const policy = config.lifecycle.default_policy;
  if (!policy || policy.mode === "permanent") {
    return undefined;
  }
  return JSON.stringify({
    mode: policy.mode,
    action: policy.action,
    ttl_seconds: policy.ttl_seconds,
  });
}

export function UploadPage({ config }: Props) {
  const { t } = useI18n();
  const { modal, message: messageApi } = App.useApp();
  const [bucket, setBucket] = useState(config.uploads.default_bucket);
  const [prefix, setPrefix] = useState("");
  const [lifecycle, setLifecycle] = useState<string | undefined>(() =>
    defaultLifecycle(config),
  );
  const [items, setItems] = useState<QueueFile[]>([]);
  const [busy, setBusy] = useState(false);
  const workers = useRef(new Set<string>());
  // 本次会话内已选中的文件 blob；页面刷新后丢失，需用户重新选择（docs 18.4）。
  const blobs = useRef(new Map<string, File>());

  useEffect(() => {
    void pruneCompletedHistory()
      .then(() => loadQueued())
      .then(setItems);
  }, []);

  const refresh = useCallback(async () => {
    setItems(await loadQueued());
  }, []);

  const handleClearCompleted = useCallback(() => {
    const count = items.filter((item) => item.status === "completed").length;
    if (count === 0) {
      return;
    }
    modal.confirm({
      title: t("queue.clearCompletedTitle"),
      content: t("queue.clearCompletedContent", { count }),
      okText: t("common.confirm"),
      cancelText: t("common.cancel"),
      onOk: async () => {
        const removed = await clearCompleted();
        messageApi.success(t("queue.completedCleared", { count: removed }));
        await refresh();
      },
    });
  }, [items, modal, messageApi, refresh, t]);

  const enqueueFiles = useCallback(
    (files: FileList) => {
      const partSize = config.uploads.multipart.default_part_size_bytes;
      const now = Date.now();
      const entries: QueueFile[] = Array.from(files).map((file, index) => ({
        id: `${now}-${index}-${file.name}`,
        name: file.name,
        size: file.size,
        type: file.type,
        objectKey: `${prefix ? `${prefix}/` : ""}${file.name}`,
        bucket,
        lifecycle,
        status: "pending",
        progress: 0,
        partSize,
        totalParts: Math.max(1, Math.ceil(file.size / partSize)),
        completedParts: [],
      }));
      entries.forEach((entry, index) => {
        void persist(entry);
        blobs.current.set(entry.id, files[index]);
      });
      void refresh();
    },
    [bucket, prefix, lifecycle, config, refresh],
  );

  const runUpload = useCallback(
    async (entry: QueueFile) => {
      if (workers.current.has(entry.id)) {
        return;
      }
      workers.current.add(entry.id);
      setBusy(true);
      try {
        const file = blobs.current.get(entry.id) ?? null;
        if (!file) {
          // 页面刷新后 blob 丢失：提示用户重新选择原文件后再继续。
          entry.needsFile = true;
          await persist(entry);
          void refresh();
          return;
        }
        // 小于阈值的小文件走单请求直传（POST /v1/files/upload），
        // 与 SDK 行为一致；大文件才走分片（docs 16.4 上传模式）。
        if (file.size <= config.uploads.direct_upload_threshold_bytes) {
          const info = await api.uploadFile(
            file,
            {
              bucket: entry.bucket,
              objectKey: entry.objectKey,
              lifecycle: entry.lifecycle,
            },
            (progress) => {
              entry.progress = progress;
              void persist(entry);
              void refresh();
            },
          );
          entry.status = "completed";
          entry.fileId = info.id;
          entry.progress = 1;
          await persist(entry);
          void refresh();
          return;
        }
        await uploadQueuedFile(file, entry, () => void refresh());
      } catch (error) {
        entry.status = "failed";
        if (error instanceof api.ApiError && error.code === "OBJECT_ALREADY_EXISTS") {
          entry.error = t("queue.errObjectExists", { path: `${entry.bucket}/${entry.objectKey}` });
        } else {
          entry.error = error instanceof Error ? error.message : String(error);
        }
        await persist(entry);
        void refresh();
      } finally {
        workers.current.delete(entry.id);
        setBusy(false);
      }
    },
    [config, refresh, t],
  );

  const reselect = useCallback(
    async (entry: QueueFile) => {
      const file = await fetchFromInput(entry);
      if (file) {
        blobs.current.set(entry.id, file);
        entry.needsFile = false;
        await persist(entry);
        messageApi.success(t("queue.reselectDone", { name: file.name }));
        void runUpload(entry);
      } else {
        messageApi.warning(t("queue.reselectCancelled"));
      }
    },
    [runUpload, messageApi, t],
  );

  // Resume pending tasks after refresh; uploads interrupted mid-flight are
  // downgraded to pending and re-attach their file via reselect (docs 18.4).
  useEffect(() => {
    void loadQueued().then((queued) => {
      queued.forEach((entry) => {
        if (entry.status === "pending" || entry.status === "uploading") {
          if (entry.status === "uploading") {
            entry.status = "pending";
            void persist(entry);
          }
          void runUpload(entry);
        }
      });
    });
  }, [runUpload]);

  // Auto-start newly queued files; blob is still in memory this session.
  // Files restored after a refresh have needsFile=true and wait for reselect.
  useEffect(() => {
    items.forEach((entry) => {
      if (entry.status === "pending" && !entry.needsFile) {
        void runUpload(entry);
      }
    });
  }, [items, runUpload]);

  return (
    <div className="page">
      <h1>{t("upload.title")}</h1>
      <Space wrap style={{ margin: "16px 0" }}>
        <span>
          {t("upload.bucket")}
          <Select
            value={bucket}
            onChange={setBucket}
            options={config.uploads.allowed_buckets.map((name) => ({ value: name, label: name }))}
            style={{ width: 180 }}
          />
        </span>
        <span>
          {t("upload.prefix")}
          <Input
            value={prefix}
            onChange={(event) => setPrefix(event.target.value)}
            placeholder={t("upload.prefixPlaceholder")}
            allowClear
            style={{ width: 220 }}
          />
        </span>
        <span>
          {t("upload.lifecycle")}
          <LifecycleSelect config={config} value={lifecycle} onChange={setLifecycle} />
        </span>
      </Space>
      <FileDrop onFiles={enqueueFiles} directory disabled={busy} />
      <UploadQueue
        items={items}
        onPause={(item) => void pauseUpload(item).then(refresh)}
        onResume={(item) => void runUpload(item)}
        onReselect={(item) => void reselect(item)}
        onCancel={(item) => void cancelUpload(item).then(refresh)}
        onRetry={(item) => void runUpload(item)}
        onClearCompleted={handleClearCompleted}
      />
    </div>
  );
}

async function fetchFromInput(entry: QueueFile): Promise<File | null> {
  // 目录条目需要 webkitdirectory 才能保留相对路径（docs 18.4）。
  const input = document.createElement("input");
  input.type = "file";
  if (entry.name.includes("/")) {
    input.setAttribute("webkitdirectory", "");
  }
  input.style.display = "none";
  document.body.appendChild(input);
  try {
    const selected = await new Promise<FileList | null>((resolve) => {
      input.addEventListener("cancel", () => resolve(null));
      input.onchange = () => resolve(input.files);
      // 必须挂载到 DOM，否则 click() 不会打开文件选择器。
      input.click();
    });
    if (!selected) {
      return null;
    }
    const files = Array.from(selected);
    if (files.length === 0) {
      return null;
    }
    // 优先取与原文件名一致的条目；不一致时降级使用所选文件，
    // 避免用户重选的文件名不同导致"点了没反应"。
    return files.find((file) => file.name === entry.name) ?? files[0];
  } finally {
    input.remove();
  }
}
