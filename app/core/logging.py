"""Structured JSON logging with redaction of sensitive headers."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.models import LogCenterConfig

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[str | None] = ContextVar("span_id", default=None)
parent_id_var: ContextVar[str | None] = ContextVar("parent_id", default=None)
node_id_var: ContextVar[str | None] = ContextVar("node_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(UTC).isoformat()
        payload: dict[str, object] = {
            "ts": ts,
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for name, var in (
            ("request_id", request_id_var),
            ("trace_id", trace_id_var),
            ("span_id", span_id_var),
            ("parent_id", parent_id_var),
            ("node_id", node_id_var),
        ):
            value = var.get()
            if value:
                payload[name] = value
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    log_center: LogCenterConfig | None = None,
) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    if log_center is not None and log_center.enabled:
        attach_log_center_handlers(log_center)


def attach_log_center_handlers(config: LogCenterConfig) -> None:
    """Attach best-effort remote log delivery to IKC Log Center (HTTP POST /ingest)."""
    if not config.url:
        logging.getLogger(__name__).warning(
            "log_center.enabled is true but url is not configured; remote delivery disabled"
        )
        return
    if config.delivery != "api":
        logging.getLogger(__name__).warning(
            "log_center.delivery=%s is not supported; only 'api' (HTTP POST /ingest) is available",
            config.delivery,
        )
        return
    try:
        from log_center_sdk.handlers import HttpLogHandler
    except ImportError:
        logging.getLogger(__name__).warning(
            "ikc-log-center is not installed (pip install pyuploadx-server[log-center]); "
            "remote log delivery disabled"
        )
        return
    try:
        handler = HttpLogHandler(
            endpoint=config.url,
            timeout=config.timeout_seconds,
            queue_size=config.queue_size,
            batch_size=config.batch_size,
            token=config.token or "",
        )
        handler.setFormatter(JsonFormatter())
        logging.getLogger().addHandler(handler)
        logging.getLogger(__name__).info(
            "log center HTTP delivery attached",
            extra={"extra_fields": {"endpoint": config.url}},
        )
    except Exception:
        logging.getLogger(__name__).exception("failed to attach log center handler")


def redact_value(value: str) -> str:
    if not value:
        return value
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
