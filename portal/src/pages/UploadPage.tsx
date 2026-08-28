import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import { FileDrop } from "../components/FileDrop";
import { UploadQueue } from "../components/UploadQueue";
import {
  cancelUpload,
  loadQueued,
  pauseUpload,
  persist,
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
  return JSON.stringify({ mode: "ttl", ttl_seconds: 30 * 86400, action: "delete" });
}

export function UploadPage({ config }: Props) {
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
    void loadQueued().then(setItems);
  }, []);

  const refresh = useCallback(async () => {
    setItems(await loadQueued());
  }, []);

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
        await uploadQueuedFile(file, entry, () => void refresh());
      } catch (error) {
        entry.status = "failed";
        entry.error = error instanceof Error ? error.message : String(error);
        await persist(entry);
        void refresh();
      } finally {
        workers.current.delete(entry.id);
        setBusy(false);
      }
    },
    [refresh],
  );

  const reselect = useCallback(
    async (entry: QueueFile) => {
      const file = await fetchFromInput(entry);
      if (file) {
        blobs.current.set(entry.id, file);
        entry.needsFile = false;
        await persist(entry);
        void runUpload(entry);
      }
    },
    [runUpload],
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

  return (
    <div className="page">
      <h1>文件上传</h1>
      <div className="controls">
        <label>
          Bucket
          <select value={bucket} onChange={(event) => setBucket(event.target.value)}>
            {config.uploads.allowed_buckets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          目标前缀
          <input
            value={prefix}
            onChange={(event) => setPrefix(event.target.value)}
            placeholder="例如 artists/10001"
          />
        </label>
        <label>
          生命周期
          <select value={lifecycle ?? ""} onChange={(event) => setLifecycle(event.target.value || undefined)}>
            <option value="">永久</option>
            {config.lifecycle.allowed_modes.map((mode) => (
              <option key={mode} value={JSON.stringify({ mode, ttl_seconds: 30 * 86400 })}>
                {mode}
              </option>
            ))}
          </select>
        </label>
      </div>
      <FileDrop onFiles={enqueueFiles} directory disabled={busy} />
      <UploadQueue
        items={items}
        onPause={(item) => void pauseUpload(item).then(refresh)}
        onResume={(item) => void runUpload(item)}
        onReselect={(item) => void reselect(item)}
        onCancel={(item) => void cancelUpload(item).then(refresh)}
        onRetry={(item) => void runUpload(item)}
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
      input.onchange = () => resolve(input.files);
      // 必须挂载到 DOM，否则 click() 不会打开文件选择器。
      input.click();
    });
    if (!selected) {
      return null;
    }
    return Array.from(selected).find((file) => file.name === entry.name) ?? null;
  } finally {
    input.remove();
  }
}
