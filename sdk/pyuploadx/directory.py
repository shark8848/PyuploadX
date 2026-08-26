"""Directory walking and manifest entry building (docs section 13)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyuploadx.exceptions import DirectoryUploadError, ValidationError
from pyuploadx.fingerprint import fast_fingerprint
from pyuploadx.ignore import default_ignore_rules
from pyuploadx.paths import normalize_relative_path


def walk_directory(
    directory_path: Path,
    *,
    recursive: bool = True,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    symlink_policy: str = "ignore",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Walk a directory and build manifest entries (files + directories).

    Returns (files, directories) where each entry is a dict with
    entry_type/relative_path/size_bytes/fingerprint/last_modified_ns/content_type.
    """
    root = directory_path.resolve()
    rules = default_ignore_rules()
    if include:
        rules.includes = include
    if exclude:
        rules.excludes.extend(exclude)
    rules.load_ignore_file(root)

    files: list[dict[str, Any]] = []
    directories: list[dict[str, Any]] = []

    def walk(current: Path, relative: str) -> None:
        for child in sorted(current.iterdir()):
            child_relative = f"{relative}/{child.name}" if relative else child.name
            try:
                normalized = normalize_relative_path(child_relative)
            except ValidationError:
                continue
            if child.name == rules.ignore_file_name:
                continue
            if rules.is_ignored(normalized):
                continue
            if child.is_symlink():
                if symlink_policy == "ignore":
                    continue
                if symlink_policy == "error":
                    raise DirectoryUploadError(f"symlink not allowed: {child}")
                target = child.resolve()
                if not target.is_relative_to(root) and not rules.includes:
                    raise DirectoryUploadError(f"symlink escapes root: {child}")
            if child.is_dir():
                directories.append(
                    {
                        "entry_type": "directory",
                        "relative_path": normalized,
                        "size_bytes": 0,
                    }
                )
                if recursive:
                    walk(child, normalized)
            elif child.is_file():
                stat = child.stat()
                files.append(
                    {
                        "entry_type": "file",
                        "relative_path": normalized,
                        "size_bytes": stat.st_size,
                        "last_modified_ns": stat.st_mtime_ns,
                        "fingerprint": fast_fingerprint(child),
                        "content_type": "application/octet-stream",
                    }
                )

    walk(root, "")
    return files, directories
