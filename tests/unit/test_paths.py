"""Path normalization tests (docs section 13.2, 29.1)."""

from __future__ import annotations

import pytest

from app.core.errors import InvalidRelativePathError
from app.directory_upload.paths import join_prefix, normalize_relative_path


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("README.md", "README.md"),
        ("./a/b.txt", "a/b.txt"),
        ("a\\b\\c.txt", "a/b/c.txt"),
        ("a//b///c.txt", "a/b/c.txt"),
        ("images/cover.jpg", "images/cover.jpg"),
        ("ü/文件.txt", "ü/文件.txt"),
    ],
)
def test_normalize_accepts(raw, expected):
    assert normalize_relative_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "../secret.txt",
        "/absolute/path",
        "C:\\absolute\\path",
        "a/../../secret",
        "a/\x00b",
        "a/\x1fb",
        "a/..",
        "..",
    ],
)
def test_normalize_rejects(raw):
    with pytest.raises(InvalidRelativePathError):
        normalize_relative_path(raw)


def test_join_prefix():
    assert join_prefix("artists/10001", "images/cover.jpg") == "artists/10001/images/cover.jpg"
    assert join_prefix("", "a.txt") == "a.txt"
    assert join_prefix("prefix/", "a.txt") == "prefix/a.txt"
