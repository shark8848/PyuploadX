"""Gitignore-style pattern matching for include/exclude and .uploadignore."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path


def _match(pattern: str, relative_path: str) -> bool:
    pattern = pattern.rstrip("/")
    if pattern.startswith("/"):
        pattern = pattern[1:]
    if "/" not in pattern and "/" in relative_path:
        return fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(
            relative_path, f"**/{pattern}"
        )
    return fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(relative_path, f"**/{pattern}")


@dataclass
class IgnoreRules:
    excludes: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    ignore_file_name: str = ".uploadignore"

    def is_ignored(self, relative_path: str) -> bool:
        for pattern in self.includes:
            if _match(pattern, relative_path):
                return False
        for pattern in self.excludes:
            if _match(pattern, relative_path):
                return True
        return False

    def load_ignore_file(self, directory: Path) -> None:
        ignore_file = directory / self.ignore_file_name
        if not ignore_file.exists():
            return
        for line in ignore_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self.excludes.append(line)


def default_ignore_rules() -> IgnoreRules:
    return IgnoreRules(
        excludes=[
            ".git/**",
            "**/.DS_Store",
            "**/__pycache__/**",
            "**/*.tmp",
        ]
    )
