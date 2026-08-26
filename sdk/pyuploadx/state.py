"""Per-file upload state persisted under ~/.pyuploadx/uploads/files (docs 12.4)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

FORBIDDEN_STATE_FIELDS = {"api_key", "bearer_token", "access_key", "secret_key", "presigned_url"}


@dataclass
class FileUploadState:
    upload_id: str
    file_path: str
    bucket: str
    object_key: str
    total_size: int
    part_size: int
    total_parts: int
    fingerprint: str
    completed_parts: set[int] = field(default_factory=set)
    status: str = "initiated"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "completed_parts": sorted(self.completed_parts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileUploadState:
        data = dict(data)
        data["completed_parts"] = set(data.get("completed_parts", []))
        return cls(**data)


class StateStore:
    def __init__(self, state_dir: str | Path) -> None:
        self.root = Path(state_dir).expanduser()
        self.files_root = self.root / "uploads" / "files"
        self.directories_root = self.root / "uploads" / "directories"
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.directories_root.mkdir(parents=True, exist_ok=True)

    def _path(self, upload_id: str) -> Path:
        return self.files_root / f"{upload_id}.json"

    def save(self, state: FileUploadState) -> None:
        payload = state.to_dict()
        for forbidden in FORBIDDEN_STATE_FIELDS:
            payload.pop(forbidden, None)
        path = self._path(state.upload_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def load(self, upload_id: str) -> FileUploadState | None:
        path = self._path(upload_id)
        if not path.exists():
            return None
        return FileUploadState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def delete(self, upload_id: str) -> None:
        self._path(upload_id).unlink(missing_ok=True)
