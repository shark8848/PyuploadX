/**
 * Portal API client. The login token is persisted in localStorage so the
 * session survives browser restarts (docs 18.5). OIDC Authorization Code +
 * PKCE is the recommended production flow; the token callback is the
 * integration point.
 */

export interface ClientConfig {
  service: { name: string; version: string };
  uploads: {
    maximum_file_size_bytes: number;
    default_mode: string;
    direct_upload_threshold_bytes: number;
    multipart: {
      enabled: boolean;
      default_part_size_bytes: number;
      minimum_part_size_bytes: number;
      maximum_part_size_bytes: number;
      maximum_parts: number;
      maximum_presign_batch_size: number;
    };
    session: { expires_after_seconds: number; refresh_enabled: boolean };
    allowed_buckets: string[];
    default_bucket: string;
  };
  storage: {
    backend: string;
    capabilities: {
      multipart: boolean;
      presigned_put: boolean;
      presigned_get: boolean;
      presigned_upload_part: boolean;
    };
  };
  presign: {
    default_expires_seconds: number;
    maximum_expires_seconds: number;
  };
  lifecycle: {
    enabled: boolean;
    allowed_modes: string[];
    allowed_actions: string[];
    permanent_allowed: boolean;
    minimum_ttl_seconds: number;
    maximum_ttl_seconds: number;
    default_policy?: { mode: string; ttl_seconds?: number; action?: string };
  };
  directory_upload: {
    enabled: boolean;
    limits: Record<string, number>;
    conflicts: { default_policy: string; allowed_policies: string[] };
  };
}

export interface FileInfo {
  id: string;
  bucket: string;
  object_key: string;
  original_filename: string;
  size_bytes: number;
  content_type?: string;
  etag?: string;
  status: string;
  lifecycle_mode?: string;
  expires_at?: string;
  completed_at?: string;
  created_at?: string;
}

export interface FilePage {
  items: FileInfo[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListFilesParams {
  bucket?: string;
  prefix?: string;
  status?: string;
  limit?: number;
  offset?: number;
  sortBy?: "name" | "created_at";
}

export interface UploadSession {
  id: string;
  bucket: string;
  object_key: string;
  original_filename: string;
  total_size: number;
  part_size: number;
  total_parts: number;
  upload_mode: string;
  backend: string;
  status: string;
  effective_lifecycle?: Record<string, unknown>;
}

let apiToken: string | null = null;
let cachedConfig: ClientConfig | null = null;

export function setApiToken(token: string | null): void {
  apiToken = token;
  cachedConfig = null;
}

/**
 * Probes whether the current browser context is already authenticated
 * (e.g. the portal nginx injects a valid X-API-Key). A 401 means the app
 * should show the login page instead of auto-entering.
 */
export async function probeAuthenticated(): Promise<boolean> {
  try {
    await request("/v1/files?limit=1");
    return true;
  } catch {
    return false;
  }
}

export function verifyApiKey(key: string): Promise<unknown> {
  return request("/v1/files?limit=1", { headers: { "X-API-Key": key } });
}

export function hasApiToken(): boolean {
  return apiToken !== null && apiToken !== "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (apiToken) {
    headers.set("X-API-Key", apiToken);
  }
  headers.set("X-Request-ID", crypto.randomUUID());
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    throw new Error("AUTHENTICATION_REQUIRED");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = body?.error ?? {};
    throw new Error(error.code ?? `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchConfig(): Promise<ClientConfig> {
  if (cachedConfig) {
    return cachedConfig;
  }
  cachedConfig = await request<ClientConfig>("/v1/client-config");
  return cachedConfig;
}

export async function refreshConfig(): Promise<ClientConfig> {
  cachedConfig = null;
  return fetchConfig();
}

export interface StorageInfo {
  backend: string;
  capabilities: {
    multipart: boolean;
    presigned_put: boolean;
    presigned_get: boolean;
    presigned_upload_part: boolean;
    list_parts: boolean;
  };
  allowed_buckets: string[];
  root_path?: string;
  multipart_path?: string;
  endpoint?: string | null;
  public_endpoint?: string | null;
  region?: string;
  access_key_configured?: boolean;
  force_path_style?: boolean;
}

export interface RuntimeSettings {
  storage: {
    default_bucket: string;
    presign_default_expires_seconds: number;
    maximum_expires_seconds: number;
    info: StorageInfo;
  };
  uploads: {
    maximum_file_size_bytes: number;
    direct_upload_threshold_bytes: number;
    default_mode: string;
    multipart: {
      default_part_size_bytes: number;
      minimum_part_size_bytes: number;
      maximum_part_size_bytes: number;
      maximum_parts: number;
    };
    session: {
      expires_after_seconds: number;
      maximum_lifetime_seconds: number;
    };
  };
  lifecycle: {
    default_policy: { mode: string; action: string; ttl_seconds: number };
    allowed_modes: string[];
    allowed_actions: string[];
    permanent_allowed: boolean;
    minimum_ttl_seconds: number;
    maximum_ttl_seconds: number;
  };
}

export type SettingsUpdate = Partial<{
  storage: Partial<Pick<RuntimeSettings["storage"], "default_bucket" | "presign_default_expires_seconds">>;
  uploads: Partial<{
    maximum_file_size_bytes: number;
    direct_upload_threshold_bytes: number;
    default_mode: string;
    multipart: Partial<Pick<RuntimeSettings["uploads"]["multipart"], "default_part_size_bytes">>;
    session: Partial<Pick<RuntimeSettings["uploads"]["session"], "expires_after_seconds">>;
  }>;
  lifecycle: Partial<{
    default_policy: Partial<RuntimeSettings["lifecycle"]["default_policy"]>;
  }>;
}>;

export async function listBuckets(): Promise<string[]> {
  const data = await request<{ buckets: string[] }>("/v1/buckets");
  return data.buckets;
}

export function createBucket(name: string): Promise<{ name: string }> {
  return request<{ name: string }>("/v1/buckets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function getSettings(): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/v1/settings");
}

export function updateSettings(update: SettingsUpdate): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/v1/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export function uploadFile(
  file: File,
  opts: { bucket: string; objectKey: string; lifecycle?: string },
  onProgress: (progress: number) => void,
): Promise<FileInfo> {
  const form = new FormData();
  form.append("file", file);
  form.append("bucket", opts.bucket);
  form.append("object_key", opts.objectKey);
  if (opts.lifecycle) {
    form.append("lifecycle", opts.lifecycle);
  }
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/v1/files/upload");
    if (apiToken) {
      xhr.setRequestHeader("X-API-Key", apiToken);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(event.loaded / event.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as FileInfo);
      } else {
        reject(new Error(xhr.responseText));
      }
    };
    xhr.onerror = () => reject(new Error("network error"));
    xhr.send(form);
  });
}

export function createUploadSession(
  opts: {
    bucket: string;
    objectKey: string;
    totalSize: number;
    partSize: number;
    lifecycle?: string;
  },
): Promise<UploadSession> {
  return request<UploadSession>("/v1/uploads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      bucket: opts.bucket,
      object_key: opts.objectKey,
      total_size: opts.totalSize,
      part_size: opts.partSize,
      upload_mode: "automatic",
      lifecycle: opts.lifecycle ? JSON.parse(opts.lifecycle) : undefined,
    }),
  });
}

export function uploadPart(
  uploadId: string,
  partNumber: number,
  blob: Blob,
  sha256: string,
  onProgress: (progress: number) => void,
): Promise<{ etag: string; size_bytes: number; checksum_sha256: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/v1/uploads/${uploadId}/parts/${partNumber}`);
    if (apiToken) {
      xhr.setRequestHeader("X-API-Key", apiToken);
    }
    xhr.setRequestHeader("X-Part-SHA256", sha256);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(event.loaded / event.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(xhr.responseText));
      }
    };
    xhr.onerror = () => reject(new Error("network error"));
    xhr.send(blob);
  });
}

export function completeUpload(uploadId: string): Promise<FileInfo> {
  return request<FileInfo>(`/v1/uploads/${uploadId}/complete`, { method: "POST" });
}

export function abortUpload(uploadId: string): Promise<unknown> {
  return request(`/v1/uploads/${uploadId}/abort`, { method: "POST" });
}

export function resumeUpload(uploadId: string): Promise<{ missing_parts: number[] }> {
  return request<{ missing_parts: number[] }>(`/v1/uploads/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId }),
  });
}

export function downloadUrl(fileId: string): string {
  return `/v1/files/${fileId}/download`;
}

export async function downloadFile(fileId: string): Promise<Blob> {
  const headers = new Headers();
  if (apiToken) {
    headers.set("X-API-Key", apiToken);
  }
  headers.set("X-Request-ID", crypto.randomUUID());
  const response = await fetch(downloadUrl(fileId), { headers });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.blob();
}

export function listFiles(params: ListFilesParams = {}): Promise<FilePage> {
  const query = new URLSearchParams();
  if (params.bucket) {
    query.set("bucket", params.bucket);
  }
  if (params.prefix) {
    query.set("prefix", params.prefix);
  }
  if (params.status) {
    query.set("status", params.status);
  }
  query.set("limit", String(params.limit ?? 50));
  query.set("offset", String(params.offset ?? 0));
  query.set("sort_by", params.sortBy ?? "name");
  return request<FilePage>(`/v1/files?${query.toString()}`);
}

export function presignDownloadUrl(fileId: string, expiresSeconds = 900): Promise<{ url: string }> {
  return request<{ url: string }>(`/v1/files/${fileId}/presign-download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expires_seconds: expiresSeconds }),
  });
}

export function deleteFile(fileId: string): Promise<unknown> {
  return request(`/v1/files/${fileId}`, { method: "DELETE" });
}

export function sha256Blob(blob: Blob): Promise<string> {
  return blob.arrayBuffer().then((buffer) => crypto.subtle.digest("SHA-256", buffer))
    .then((digest) =>
      Array.from(new Uint8Array(digest))
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join(""),
    );
}
