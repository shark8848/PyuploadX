"""Retry policy tests (docs 12.5)."""

from __future__ import annotations

from pyuploadx.exceptions import ServerError
from pyuploadx.retry import exponential_delay, is_retryable_exception, retry


def test_exponential_delay_with_jitter():
    assert 0 < exponential_delay(0, base_delay=1.0, max_delay=30.0) <= 2.0
    assert 0 < exponential_delay(10, base_delay=1.0, max_delay=30.0) <= 31.0


def test_retry_succeeds_after_transient_failures(monkeypatch):
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            exc = ServerError("boom")
            exc.status_code = 503
            raise exc
        return "ok"

    assert retry(flaky, max_attempts=5, base_delay=0.01, max_delay=0.05) == "ok"
    assert calls["count"] == 3


def test_retry_gives_up(monkeypatch):
    def always_fails():
        exc = ServerError("boom")
        exc.status_code = 500
        raise exc

    try:
        retry(always_fails, max_attempts=2, base_delay=0.01, max_delay=0.05)
    except ServerError:
        pass
    else:
        raise AssertionError("expected ServerError")


def test_is_retryable_exception():
    exc = ServerError("x")
    exc.status_code = 503
    assert is_retryable_exception(exc)
