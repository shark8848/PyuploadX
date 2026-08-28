"""HTTP Range header parsing tests (docs 16.2)."""

from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.core.ranges import ByteRange, parse_byte_range


def test_no_header_returns_none():
    assert parse_byte_range(None, 100) is None


def test_closed_range():
    assert parse_byte_range("bytes=0-4", 100) == ByteRange(start=0, end=4)
    assert parse_byte_range("bytes=2-5", 10) == ByteRange(start=2, end=5)
    assert parse_byte_range("bytes=0-499", 1000).length == 500


def test_open_ended_range_clamps():
    assert parse_byte_range("bytes=90-", 100) == ByteRange(start=90, end=99)
    assert parse_byte_range("bytes=0-", 10) == ByteRange(start=0, end=9)
    assert parse_byte_range("bytes=8-99", 10) == ByteRange(start=8, end=9)


def test_suffix_range():
    assert parse_byte_range("bytes=-5", 100) == ByteRange(start=95, end=99)
    assert parse_byte_range("bytes=-200", 100) == ByteRange(start=0, end=99)


@pytest.mark.parametrize(
    "header",
    [
        "bytes=100-",
        "bytes=10-",
        "bytes=5-2",
        "bytes=abc",
        "bytes=-0",
        "items=0-4",
        "bytes=0-1,3-4",
    ],
)
def test_unsatisfiable_or_malformed(header):
    with pytest.raises(ApiError) as excinfo:
        parse_byte_range(header, 10)
    assert excinfo.value.status_code == 416
    assert excinfo.value.code == "RANGE_NOT_SATISFIABLE"


def test_empty_file_never_satisfiable():
    with pytest.raises(ApiError):
        parse_byte_range("bytes=0-0", 0)
