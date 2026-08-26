"""Fingerprint tests (docs 12.3)."""

from __future__ import annotations

from pyuploadx.fingerprint import fast_fingerprint, sha256_of_file


def test_fast_fingerprint_stable(tmp_path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"x" * 1000)
    assert fast_fingerprint(path) == fast_fingerprint(path)
    assert fast_fingerprint(path).startswith("fp:")


def test_fingerprint_changes_with_content(tmp_path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"x" * 1000)
    first = fast_fingerprint(path)
    path.write_bytes(b"y" * 1000)
    assert fast_fingerprint(path) != first


def test_sha256_of_file(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello")
    assert sha256_of_file(path) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
