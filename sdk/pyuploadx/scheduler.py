"""Concurrency scheduling per docs section 13.6: global/file/part semaphores."""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")


class GlobalSemaphore:
    """Global request limiter shared across all uploads."""

    def __init__(self, max_concurrent: int = 32) -> None:
        self._semaphore = threading.BoundedSemaphore(max_concurrent)

    def __enter__(self) -> GlobalSemaphore:
        self._semaphore.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self._semaphore.release()


class Scheduler:
    def __init__(
        self,
        max_workers: int = 8,
        max_concurrent_requests: int = 32,
    ) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pyuploadx")
        self._global = GlobalSemaphore(max_concurrent_requests)
        self._submitted: list[Future] = []

    def submit(self, fn: Callable[..., T], *args: object, **kwargs: object) -> Future:
        def _guarded() -> T:
            with self._global:
                return fn(*args, **kwargs)

        future = self._executor.submit(_guarded)
        self._submitted.append(future)
        return future

    def wait_all(self) -> None:
        for future in self._submitted:
            future.result()
        self._submitted.clear()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
