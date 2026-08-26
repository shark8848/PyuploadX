"""Strict configuration validation shared by startup and the config CLI."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config.models import Settings


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)

    def merge(self, other: ValidationResult) -> None:
        self.ok = self.ok and other.ok
        self.errors.extend(other.errors)


def validate_settings(settings: Settings) -> ValidationResult:
    result = ValidationResult(ok=True)

    if settings.cluster.enabled:
        url = (settings.database.url or "").lower()
        if "sqlite" in url:
            result.ok = False
            result.errors.append("cluster mode requires PostgreSQL; SQLite is forbidden")
        if settings.storage.backend == "local" and settings.storage.local.require_shared_filesystem_in_cluster:
            result.ok = False
            result.errors.append(
                "cluster mode with local storage requires a shared filesystem "
                "(set storage.local.require_shared_filesystem_in_cluster=false only for single-node)"
            )

    if settings.storage.backend == "s3":
        if not settings.storage.s3.internal_endpoint_url:
            result.ok = False
            result.errors.append("storage.s3.internal_endpoint_url is required when backend is s3")
        if not settings.storage.s3.access_key or not settings.storage.s3.secret_key:
            result.ok = False
            result.errors.append("S3 credentials must be provided via environment variables")

    if not settings.storage.allowed_buckets:
        result.ok = False
        result.errors.append("storage.allowed_buckets must not be empty")
    if settings.storage.default_bucket not in settings.storage.allowed_buckets:
        result.ok = False
        result.errors.append("storage.default_bucket must be listed in storage.allowed_buckets")

    multipart = settings.uploads.multipart
    if not (multipart.minimum_part_size_bytes <= multipart.default_part_size_bytes <= multipart.maximum_part_size_bytes):
        result.ok = False
        result.errors.append(
            "multipart.default_part_size_bytes must be within [minimum_part_size_bytes, maximum_part_size_bytes]"
        )

    rules = settings.lifecycle.policy
    if rules.minimum_ttl_seconds > rules.maximum_ttl_seconds:
        result.ok = False
        result.errors.append("lifecycle.policy.minimum_ttl_seconds must not exceed maximum_ttl_seconds")

    for policy in settings.directory_upload.conflicts.allowed_policies:
        if policy not in ("reject", "skip", "overwrite", "rename", "compare"):
            result.ok = False
            result.errors.append(f"unknown directory conflict policy: {policy}")
    if settings.directory_upload.conflicts.default_policy not in settings.directory_upload.conflicts.allowed_policies:
        result.ok = False
        result.errors.append("directory_upload.conflicts.default_policy must be in allowed_policies")

    return result
