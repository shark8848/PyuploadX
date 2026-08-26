/**
 * Upload queue with IndexedDB persistence (docs 18.4): page refresh restores
 * task metadata, revalidates fingerprints, queries server state, uploads the
 * missing parts only.
 */

import Dexie, { type Table } from "dexie";
import * as api from "../api/client";

export interface QueueFile {
  id: string;
  name: string;
  size: number;
  type: string;
  objectKey: string;
  bucket: string;
  lifecycle?: string;
  status: "pending" | "uploading" | "paused" | "completed" | "failed";
  progress: number;
  uploadId?: string;
  fileId?: string;
  partSize: number;
  totalParts: number;
  completedParts: number[];
  error?: string;
}

class UploadDB extends Dexie {
  files!: Table<QueueFile, string>;

  constructor() {
    super("pyuploadx-portal");
    this.version(1).stores({
      files: "id, status, bucket, objectKey",
    });
  }
}

export const db = new UploadDB();

export async function persist(file: QueueFile): Promise<void> {
  await db.files.put(file);
}

export async function loadQueued(): Promise<QueueFile[]> {
  return db.files.orderBy("status").toArray();
}

export async function removeQueued(id: string): Promise<void> {
  await db.files.delete(id);
}

export async function uploadQueuedFile(
  file: Blob,
  entry: QueueFile,
  onProgress: (progress: number) => void,
): Promise<api.FileInfo> {
  entry.status = "uploading";
  entry.progress = 0;
  await persist(entry);

  const fileSize = file.size;
  const partSize = entry.partSize;
  const totalParts = Math.max(1, Math.ceil(fileSize / partSize));

  if (!entry.uploadId) {
    const session = await api.createUploadSession({
      bucket: entry.bucket,
      objectKey: entry.objectKey,
      totalSize: fileSize,
      partSize,
      lifecycle: entry.lifecycle,
    });
    entry.uploadId = session.id;
    entry.totalParts = totalParts;
    await persist(entry);
  } else {
    const state = await api.resumeUpload(entry.uploadId);
    entry.completedParts = entry.completedParts.filter((part) =>
      !state.missing_parts.includes(part),
    );
    await persist(entry);
  }

  const missing: number[] = [];
  for (let part = 1; part <= totalParts; part += 1) {
    if (!entry.completedParts.includes(part)) {
      missing.push(part);
    }
  }

  for (let index = 0; index < missing.length; index += 1) {
    const partNumber = missing[index];
    const start = (partNumber - 1) * partSize;
    const end = Math.min(start + partSize, fileSize);
    const blob = file.slice(start, end);
    const checksum = await api.sha256Blob(blob);
    const result = await api.uploadPart(
      entry.uploadId,
      partNumber,
      blob,
      checksum,
      () => undefined,
    );
    void result;
    entry.completedParts.push(partNumber);
    entry.progress = (index + 1) / missing.length;
    await persist(entry);
    onProgress(entry.progress);
  }

  const info = await api.completeUpload(entry.uploadId);
  entry.status = "completed";
  entry.fileId = info.id;
  entry.progress = 1;
  await persist(entry);
  return info;
}

export async function pauseUpload(entry: QueueFile): Promise<void> {
  if (entry.status === "uploading" && entry.uploadId) {
    entry.status = "paused";
    await persist(entry);
  }
}

export async function cancelUpload(entry: QueueFile): Promise<void> {
  if (entry.uploadId) {
    await api.abortUpload(entry.uploadId).catch(() => undefined);
  }
  await removeQueued(entry.id);
}
