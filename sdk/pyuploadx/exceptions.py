"""SDK exception hierarchy per docs_product-design.md section 17.5."""

from __future__ import annotations


class UploadClientError(Exception):
    """Base class for all SDK errors."""


class AuthenticationError(UploadClientError):
    pass


class AuthorizationError(UploadClientError):
    pass


class ValidationError(UploadClientError):
    pass


class RateLimitError(UploadClientError):
    pass


class ServerError(UploadClientError):
    pass


class StorageUnavailableError(UploadClientError):
    pass


class MultipartError(UploadClientError):
    pass


class ResumeError(UploadClientError):
    pass


class DirectoryUploadError(UploadClientError):
    pass


class LifecycleError(UploadClientError):
    pass


class ChecksumMismatchError(UploadClientError):
    pass


ERROR_MAP = {
    "AUTHENTICATION_REQUIRED": AuthenticationError,
    "FORBIDDEN": AuthorizationError,
    "INVALID_BUCKET": ValidationError,
    "INVALID_FILE_SIZE": ValidationError,
    "FILE_TOO_LARGE": ValidationError,
    "INVALID_PART_NUMBER": ValidationError,
    "INVALID_PART_SIZE": ValidationError,
    "INVALID_RELATIVE_PATH": ValidationError,
    "INVALID_LIFECYCLE_POLICY": LifecycleError,
    "TTL_OUT_OF_RANGE": LifecycleError,
    "UPLOAD_NOT_FOUND": ResumeError,
    "UPLOAD_ALREADY_COMPLETED": MultipartError,
    "UPLOAD_ABORTED": ResumeError,
    "UPLOAD_EXPIRED": ResumeError,
    "UPLOAD_STATE_CONFLICT": MultipartError,
    "MISSING_PARTS": MultipartError,
    "PART_ETAG_MISMATCH": MultipartError,
    "CHECKSUM_MISMATCH": ChecksumMismatchError,
    "OBJECT_ALREADY_EXISTS": ValidationError,
    "MANIFEST_HASH_MISMATCH": DirectoryUploadError,
    "DIRECTORY_HAS_FAILED_ENTRIES": DirectoryUploadError,
    "STORAGE_CAPABILITY_NOT_SUPPORTED": MultipartError,
    "STORAGE_UNAVAILABLE": StorageUnavailableError,
    "DATABASE_UNAVAILABLE": StorageUnavailableError,
}
