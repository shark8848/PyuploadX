"""Minimal tracing facade. No-op unless OpenTelemetry is configured."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


active_trace_id: ContextVar[str | None] = ContextVar("active_trace_id", default=None)


@contextmanager
def start_span(_name: str, **_attributes: object) -> Iterator[None]:
    token = active_trace_id.set(active_trace_id.get() or "trace-unset")
    try:
        yield
    finally:
        active_trace_id.reset(token)
