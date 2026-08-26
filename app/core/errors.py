"""Unified API error model per docs_product-design.md section 16.8/16.9."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """An error that maps to a structured API error response."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.retryable = retryable


class UploadNotFoundError(ApiError):
    def __init__(self, upload_id: str) -> None:
        super().__init__(
            "UPLOAD_NOT_FOUND",
            f"Upload {upload_id} does not exist.",
            status_code=404,
        )


class UploadAlreadyCompletedError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            "UPLOAD_ALREADY_COMPLETED",
            "Upload has already been completed.",
            status_code=409,
        )


class UploadAbortedError(ApiError):
    def __init__(self) -> None:
        super().__init__("UPLOAD_ABORTED", "Upload has been aborted.", status_code=409)


class UploadExpiredError(ApiError):
    def __init__(self) -> None:
        super().__init__("UPLOAD_EXPIRED", "Upload session has expired.", status_code=410)


class UploadStateConflictError(ApiError):
    def __init__(self, message: str = "Upload is not in the required state.") -> None:
        super().__init__("UPLOAD_STATE_CONFLICT", message, status_code=409)


class InvalidPartNumberError(ApiError):
    def __init__(self, part_number: int, maximum_parts: int) -> None:
        super().__init__(
            "INVALID_PART_NUMBER",
            f"Part number {part_number} is out of range (1..{maximum_parts}).",
            details={"part_number": part_number, "maximum_parts": maximum_parts},
        )


class InvalidPartSizeError(ApiError):
    def __init__(self, size_bytes: int, minimum: int, maximum: int) -> None:
        super().__init__(
            "INVALID_PART_SIZE",
            f"Part size {size_bytes} is out of range ({minimum}..{maximum}).",
            details={"size_bytes": size_bytes, "minimum": minimum, "maximum": maximum},
        )


class MissingPartsError(ApiError):
    def __init__(self, missing_parts: list[int]) -> None:
        super().__init__(
            "MISSING_PARTS",
            "Upload cannot be completed; parts are missing.",
            status_code=409,
            details={"missing_parts": missing_parts},
        )


class PartEtagMismatchError(ApiError):
    def __init__(self, part_number: int) -> None:
        super().__init__(
            "PART_ETAG_MISMATCH",
            f"ETag for part {part_number} does not match storage.",
            status_code=409,
            details={"part_number": part_number},
        )


class ChecksumMismatchError(ApiError):
    def __init__(self, message: str = "Checksum verification failed.") -> None:
        super().__init__("CHECKSUM_MISMATCH", message, status_code=409)


class ObjectAlreadyExistsError(ApiError):
    def __init__(self, bucket: str, object_key: str) -> None:
        super().__init__(
            "OBJECT_ALREADY_EXISTS",
            f"Object {bucket}/{object_key} already exists.",
            status_code=409,
            details={"bucket": bucket, "object_key": object_key},
        )


class InvalidRelativePathError(ApiError):
    def __init__(self, message: str = "Invalid relative path.") -> None:
        super().__init__("INVALID_RELATIVE_PATH", message, status_code=422)


class DuplicateNormalizedPathError(ApiError):
    def __init__(self, path: str) -> None:
        super().__init__(
            "DUPLICATE_NORMALIZED_PATH",
            f"Duplicate normalized path: {path}",
            status_code=409,
            details={"path": path},
        )


class ManifestIncompleteError(ApiError):
    def __init__(self, message: str = "Manifest is incomplete.") -> None:
        super().__init__("MANIFEST_INCOMPLETE", message, status_code=409)


class ManifestHashMismatchError(ApiError):
    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            "MANIFEST_HASH_MISMATCH",
            "Manifest hash does not match.",
            status_code=409,
            details={"expected": expected, "actual": actual},
        )


class DirectoryManifestMismatchError(ApiError):
    def __init__(self, message: str = "Directory manifest does not match entries.") -> None:
        super().__init__("DIRECTORY_MANIFEST_MISMATCH", message, status_code=409)


class DirectoryHasFailedEntriesError(ApiError):
    def __init__(self, failed: int) -> None:
        super().__init__(
            "DIRECTORY_HAS_FAILED_ENTRIES",
            f"Directory upload has {failed} failed entries.",
            status_code=409,
            details={"failed_entries": failed},
        )


class InvalidLifecyclePolicyError(ApiError):
    def __init__(self, message: str = "Invalid lifecycle policy.") -> None:
        super().__init__("INVALID_LIFECYCLE_POLICY", message, status_code=422)


class TtlOutOfRangeError(ApiError):
    def __init__(self, ttl_seconds: int, minimum: int, maximum: int) -> None:
        super().__init__(
            "TTL_OUT_OF_RANGE",
            f"TTL {ttl_seconds}s is outside the allowed range ({minimum}s..{maximum}s).",
            status_code=422,
            details={"ttl_seconds": ttl_seconds, "minimum": minimum, "maximum": maximum},
        )


class FileUnderLegalHoldError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            "FILE_UNDER_LEGAL_HOLD",
            "File is under legal hold and cannot be modified or deleted.",
            status_code=409,
        )


class StorageCapabilityNotSupportedError(ApiError):
    def __init__(self, capability: str) -> None:
        super().__init__(
            "STORAGE_CAPABILITY_NOT_SUPPORTED",
            f"Storage backend does not support {capability}.",
            status_code=501,
            details={"capability": capability},
        )


class StorageUnavailableError(ApiError):
    def __init__(self, message: str = "Storage backend is unavailable.") -> None:
        super().__init__(
            "STORAGE_UNAVAILABLE",
            message,
            status_code=503,
            retryable=True,
        )


class DatabaseUnavailableError(ApiError):
    def __init__(self, message: str = "Database is unavailable.") -> None:
        super().__init__(
            "DATABASE_UNAVAILABLE",
            message,
            status_code=503,
            retryable=True,
        )


class AuthenticationError(ApiError):
    def __init__(self) -> None:
        super().__init__("AUTHENTICATION_REQUIRED", "Authentication is required.", status_code=401)


class AuthorizationError(ApiError):
    def __init__(self, permission: str = "") -> None:
        suffix = f": missing permission {permission}" if permission else ""
        super().__init__("FORBIDDEN", f"Access denied.{suffix}", status_code=403)


def error_payload(
    error: ApiError,
    request_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
        }
    }
    if error.details is not None:
        body["error"]["details"] = error.details
    if request_id:
        body["error"]["request_id"] = request_id
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc, request_id),
            headers={"X-Request-ID": request_id} if request_id else None,
        )
