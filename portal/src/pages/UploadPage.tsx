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
      entries.forEach((entry) => void persist(entry));
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
        const file = await fetchFromInput(entry);
        if (!file) {
          throw new Error("file unavailable after refresh");
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

  // Resume any pending/paused tasks after refresh.
  useEffect(() => {
    void loadQueued().then((queued) => {
      queued
        .filter((entry) => entry.status === "pending")
        .forEach((entry) => void runUpload(entry));
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
        onCancel={(item) => void cancelUpload(item).then(refresh)}
        onRetry={(item) => void runUpload(item)}
      />
    </div>
  );
}

async function fetchFromInput(entry: QueueFile): Promise<File | null> {
  const input = document.createElement("input");
  input.type = "file";
  const selected = await new Promise<FileList | null>((resolve) => {
    input.onchange = () => resolve(input.files);
    input.click();
  });
  if (!selected) {
    return null;
  }
  return Array.from(selected).find((file) => file.name === entry.name) ?? null;
}
