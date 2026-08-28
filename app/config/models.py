"""Pydantic configuration models mirroring docs_product-design.md section 19."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AppConfig(BaseModel):
    name: str = "upload-service"
    environment: str = "development"
    version: str = "1.4.0"
    debug: bool = False


class ServerTimeouts(BaseModel):
    request_seconds: int = 300
    keep_alive_seconds: int = 10
    graceful_shutdown_seconds: int = 60


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 2
    proxy_headers: bool = True
    timeouts: ServerTimeouts = Field(default_factory=ServerTimeouts)


class ApiKeyAuthConfig(BaseModel):
    header_name: str = "X-API-Key"
    keys_from_env: str = "UPLOAD_API_KEYS"


class AuthConfig(BaseModel):
    mode: Literal["api_key", "none"] = "api_key"
    api_key: ApiKeyAuthConfig = Field(default_factory=ApiKeyAuthConfig)


class DatabaseConfig(BaseModel):
    url_from_env: str = "UPLOAD_DATABASE_URL"
    url: str | None = None
    pool_size: int = 20
    max_overflow: int = 20
    pool_timeout_seconds: int = 30
    pool_recycle_seconds: int = 1800


class RedisConfig(BaseModel):
    enabled: bool = True
    url_from_env: str = "UPLOAD_REDIS_URL"
    url: str | None = None
    key_prefix: str = "upload-service"


class LocalStorageConfig(BaseModel):
    root_path: str = "/data/storage"
    multipart_path: str = "/data/storage/.multipart"
    require_shared_filesystem_in_cluster: bool = True
    fsync: bool = True


class S3StorageConfig(BaseModel):
    internal_endpoint_url: str | None = None
    public_endpoint_url: str | None = None
    region: str = "us-east-1"
    access_key_from_env: str = "S3_ACCESS_KEY"
    secret_key_from_env: str = "S3_SECRET_KEY"
    access_key: str | None = None
    secret_key: str | None = None
    force_path_style: bool = True
    use_ssl: bool = False
    verify_ssl: bool = False
    max_pool_connections: int = 100


class StorageConfig(BaseModel):
    backend: Literal["local", "s3"] = "s3"
    default_bucket: str = "app-default"
    allowed_buckets: list[str] = ["app-default", "public-assets"]
    local: LocalStorageConfig = Field(default_factory=LocalStorageConfig)
    s3: S3StorageConfig = Field(default_factory=S3StorageConfig)


class MultipartConfig(BaseModel):
    enabled: bool = True
    default_part_size_bytes: int = 8 * 1024 * 1024
    minimum_part_size_bytes: int = 5 * 1024 * 1024
    maximum_part_size_bytes: int = 512 * 1024 * 1024
    maximum_parts: int = 10000
    maximum_presign_batch_size: int = 100


class SessionConfig(BaseModel):
    expires_after_seconds: int = 86400
    maximum_lifetime_seconds: int = 604800
    refresh_enabled: bool = True


class FileSizeConfig(BaseModel):
    maximum_bytes: int = 5 * 1024 * 1024 * 1024


class UploadsConfig(BaseModel):
    default_mode: Literal["automatic", "proxy", "presigned"] = "automatic"
    direct_upload_threshold_bytes: int = 20 * 1024 * 1024
    object_conflict_policy: str = "reject"
    multipart: MultipartConfig = Field(default_factory=MultipartConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    file_size: FileSizeConfig = Field(default_factory=FileSizeConfig)


class PresignConfig(BaseModel):
    default_expires_seconds: int = 900
    maximum_expires_seconds: int = 86400
    upload_part_expires_seconds: int = 3600


class PermanentLinkConfig(BaseModel):
    enabled: bool = True
    secret_from_env: str = "UPLOAD_PERMANENT_LINK_SECRET"
    secret: str | None = None


class DirectoryUploadLimits(BaseModel):
    maximum_files_per_job: int = 1_000_000
    maximum_directories_per_job: int = 100_000
    maximum_total_bytes: int = 1024**4
    maximum_path_depth: int = 64
    maximum_relative_path_bytes: int = 1024
    maximum_entries_per_manifest_request: int = 1000


class DirectoryIgnoreConfig(BaseModel):
    file_name: str = ".uploadignore"
    defaults: list[str] = [
        ".git/**",
        "**/.DS_Store",
        "**/__pycache__/**",
        "**/*.tmp",
    ]


class DirectorySymlinksConfig(BaseModel):
    policy: Literal["ignore", "error", "follow_files", "follow_all"] = "ignore"
    allow_outside_root: bool = False
    detect_cycles: bool = True


class DirectoryConflictsConfig(BaseModel):
    default_policy: Literal["reject", "skip", "overwrite", "rename", "compare"] = "reject"
    allowed_policies: list[str] = ["reject", "skip", "overwrite", "rename", "compare"]


class DirectoryLifecycleConfig(BaseModel):
    allow_entry_override: bool = True
    starts_at: Literal["file_completed", "directory_completed"] = "file_completed"


class DirectoryUploadConfig(BaseModel):
    enabled: bool = True
    limits: DirectoryUploadLimits = Field(default_factory=DirectoryUploadLimits)
    upload: dict[str, int] = Field(
        default_factory=lambda: {
            "default_file_concurrency": 8,
            "maximum_file_concurrency": 32,
            "default_part_concurrency": 4,
            "maximum_part_concurrency": 16,
            "maximum_total_concurrent_requests": 32,
        }
    )
    ignore: DirectoryIgnoreConfig = Field(default_factory=DirectoryIgnoreConfig)
    symlinks: DirectorySymlinksConfig = Field(default_factory=DirectorySymlinksConfig)
    conflicts: DirectoryConflictsConfig = Field(default_factory=DirectoryConflictsConfig)
    lifecycle: DirectoryLifecycleConfig = Field(default_factory=DirectoryLifecycleConfig)


class LifecycleDefaultPolicy(BaseModel):
    mode: Literal["permanent", "ttl", "expires_at", "temporary", "sliding_ttl"] = "ttl"
    ttl_seconds: int = 2_592_000
    action: Literal["delete", "notify", "none"] = "delete"


class LifecyclePolicyRules(BaseModel):
    allow_client_override: bool = True
    permanent_allowed: bool = True
    minimum_ttl_seconds: int = 3600
    maximum_ttl_seconds: int = 31_536_000
    allowed_modes: list[str] = ["temporary", "ttl", "expires_at", "permanent", "sliding_ttl"]
    allowed_actions: list[str] = ["delete", "notify", "none"]


class LifecycleWorkerConfig(BaseModel):
    enabled: bool = True
    scan_interval_seconds: int = 60
    batch_size: int = 200
    concurrency: int = 8


class LifecycleConfig(BaseModel):
    enabled: bool = True
    default_policy: LifecycleDefaultPolicy = Field(default_factory=LifecycleDefaultPolicy)
    policy: LifecyclePolicyRules = Field(default_factory=LifecyclePolicyRules)
    worker: LifecycleWorkerConfig = Field(default_factory=LifecycleWorkerConfig)


class CORSConfig(BaseModel):
    allow_credentials: bool = True
    allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers: list[str] = [
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "Idempotency-Key",
        "X-Part-SHA256",
        "X-Request-ID",
    ]
    expose_headers: list[str] = ["ETag", "X-Request-ID"]


class PortalConfig(BaseModel):
    enabled: bool = True
    public_base_url: str = "https://upload.example.com"
    origins: list[str] = ["https://upload.example.com"]
    cors: CORSConfig = Field(default_factory=CORSConfig)


class ClusterReadinessConfig(BaseModel):
    check_database: bool = True
    check_redis: bool = True
    check_storage: bool = True


class ClusterConfig(BaseModel):
    enabled: bool = True
    node_id_from_env: str = "HOSTNAME"
    node_id: str | None = None
    readiness: ClusterReadinessConfig = Field(default_factory=ClusterReadinessConfig)


class WorkerCleanupConfig(BaseModel):
    enabled: bool = True
    interval_seconds: int = 300
    batch_size: int = 100


class WorkerConfig(BaseModel):
    enabled: bool = True
    cleanup: WorkerCleanupConfig = Field(default_factory=WorkerCleanupConfig)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: Literal["json", "text"] = "json"
    redact_headers: list[str] = ["Authorization", "X-API-Key", "Cookie"]


class MetricsConfig(BaseModel):
    enabled: bool = True
    path: str = "/metrics"


class TracingConfig(BaseModel):
    enabled: bool = False
    service_name: str = "upload-service"
    otlp_endpoint: str | None = None


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    uploads: UploadsConfig = Field(default_factory=UploadsConfig)
    presign: PresignConfig = Field(default_factory=PresignConfig)
    permanent_link: PermanentLinkConfig = Field(default_factory=PermanentLinkConfig)
    directory_upload: DirectoryUploadConfig = Field(default_factory=DirectoryUploadConfig)
    lifecycle: LifecycleConfig = Field(default_factory=LifecycleConfig)
    portal: PortalConfig = Field(default_factory=PortalConfig)
    cluster: ClusterConfig = Field(default_factory=ClusterConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)

    def resolve_secrets(self) -> None:
        """Resolve values that reference environment variables."""
        import os

        if self.database.url is None:
            self.database.url = os.environ.get(self.database.url_from_env)
        if self.redis.url is None:
            self.redis.url = os.environ.get(self.redis.url_from_env)
        if self.storage.s3.access_key is None:
            self.storage.s3.access_key = os.environ.get(self.storage.s3.access_key_from_env)
        if self.storage.s3.secret_key is None:
            self.storage.s3.secret_key = os.environ.get(self.storage.s3.secret_key_from_env)
        if self.cluster.node_id is None:
            self.cluster.node_id = os.environ.get(self.cluster.node_id_from_env, "node-unknown")
        if self.permanent_link.secret is None:
            self.permanent_link.secret = os.environ.get(self.permanent_link.secret_from_env)

    @model_validator(mode="after")
    def _validate_settings(self) -> Settings:
        self.resolve_secrets()
        return self
