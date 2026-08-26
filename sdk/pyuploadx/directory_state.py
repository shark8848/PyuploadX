"""Per-directory upload state persisted in SQLite (docs 12.4, 13)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class DirectoryState:
    def __init__(self, path: Path) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                relative_path TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                upload_id TEXT,
                file_id TEXT
            )
            """
        )
        self._conn.commit()

    def upsert_entry(
        self,
        relative_path: str,
        entry_type: str,
        size_bytes: int,
        status: str = "pending",
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO entries (relative_path, entry_type, size_bytes, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET
                entry_type=excluded.entry_type,
                size_bytes=excluded.size_bytes,
                status=excluded.status
            """,
            (relative_path, entry_type, size_bytes, status),
        )
        self._conn.commit()

    def mark_uploaded(self, relative_path: str, upload_id: str, file_id: str) -> None:
        self._conn.execute(
            "UPDATE entries SET status='uploaded', upload_id=?, file_id=? WHERE relative_path=?",
            (upload_id, file_id, relative_path),
        )
        self._conn.commit()

    def pending_paths(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT relative_path FROM entries WHERE status != 'uploaded' ORDER BY relative_path"
        ).fetchall()
        return [row[0] for row in rows]

    def close(self) -> None:
        self._conn.close()
