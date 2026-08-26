"""Prometheus metrics per docs_product-design.md section 23.2."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

upload_requests_total = Counter(
    "upload_requests_total",
    "Total upload API requests.",
    ["operation"],
)
upload_latency_seconds = Histogram(
    "upload_latency_seconds",
    "Upload API request latency.",
    ["operation"],
)
upload_active_sessions = Gauge(
    "upload_active_sessions",
    "Active upload sessions.",
)
upload_parts_total = Counter(
    "upload_parts_total",
    "Parts committed.",
)
upload_part_bytes_total = Counter(
    "upload_part_bytes_total",
    "Part bytes committed.",
)
upload_part_retries_total = Counter(
    "upload_part_retries_total",
    "Part retries observed.",
)
upload_resume_total = Counter(
    "upload_resume_total",
    "Resume operations.",
)
upload_complete_total = Counter(
    "upload_complete_total",
    "Completed uploads.",
)
upload_abort_total = Counter(
    "upload_abort_total",
    "Aborted uploads.",
)
upload_expired_total = Counter(
    "upload_expired_total",
    "Expired upload sessions.",
)
upload_checksum_failures_total = Counter(
    "upload_checksum_failures_total",
    "Checksum verification failures.",
)

directory_upload_jobs_total = Counter(
    "directory_upload_jobs_total",
    "Directory upload jobs created.",
)
directory_upload_active_jobs = Gauge(
    "directory_upload_active_jobs",
    "Active directory upload jobs.",
)
directory_upload_entries_total = Counter(
    "directory_upload_entries_total",
    "Directory upload entries added.",
)
directory_upload_bytes_total = Counter(
    "directory_upload_bytes_total",
    "Directory upload bytes processed.",
)
directory_upload_failed_files_total = Counter(
    "directory_upload_failed_files_total",
    "Directory upload failed entries.",
)

lifecycle_actions_total = Counter(
    "lifecycle_actions_total",
    "Lifecycle actions executed.",
    ["action"],
)
lifecycle_action_failures_total = Counter(
    "lifecycle_action_failures_total",
    "Lifecycle action failures.",
)
lifecycle_pending_files = Gauge(
    "lifecycle_pending_files",
    "Files pending lifecycle action.",
)
lifecycle_action_latency_seconds = Histogram(
    "lifecycle_action_latency_seconds",
    "Lifecycle action latency.",
)

database_pool_in_use = Gauge(
    "database_pool_in_use",
    "Database pool connections in use.",
)
database_lock_wait_seconds = Histogram(
    "database_lock_wait_seconds",
    "Database lock wait time.",
)
redis_operation_latency_seconds = Histogram(
    "redis_operation_latency_seconds",
    "Redis operation latency.",
)
storage_operation_latency_seconds = Histogram(
    "storage_operation_latency_seconds",
    "Storage operation latency.",
    ["backend", "operation"],
)
