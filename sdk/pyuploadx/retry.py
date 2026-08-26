"""Retry policy per docs_product-design.md section 12.5."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from pyuploadx.exceptions import UploadClientError

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


T = TypeVar("T")


def exponential_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """delay = min(maxDelay, baseDelay * 2^attempt) + jitter"""
    delay = min(max_delay, base_delay * (2 ** attempt))
    return delay + random.uniform(0, min(delay, 1.0))


def is_retryable_exception(exc: Exception) -> bool:
    from pyuploadx.exceptions import ServerError, StorageUnavailableError

    return isinstance(exc, (ServerError, StorageUnavailableError))


def retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_statuses: set[int] | None = None,
) -> T:
    """Retry a callable with exponential backoff and jitter."""
    statuses = retryable_statuses or RETRYABLE_STATUS_CODES
    attempt = 0
    while True:
        try:
            return fn()
        except UploadClientError as exc:
            status = getattr(exc, "status_code", None)
            if status not in statuses or attempt >= max_attempts - 1:
                raise
            attempt += 1
            time.sleep(exponential_delay(attempt, base_delay, max_delay))
        except (ConnectionError, TimeoutError):
            if attempt >= max_attempts - 1:
                raise
            attempt += 1
            time.sleep(exponential_delay(attempt, base_delay, max_delay))
