"""UploadClient per docs_product-design.md section 17.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from pyuploadx.directory import walk_directory
from pyuploadx.directory_state import DirectoryState
from pyuploadx.exceptions import (
    ERROR_MAP,
    UploadClientError,
)
from pyuploadx.fingerprint import fast_fingerprint
from pyuploadx.manifest import manifest_hash_from_entries
from pyuploadx.models import DirectoryJobInfo, FileInfo, UploadSessionInfo
from pyuploadx.multipart import upload_all_parts
from pyuploadx.paths import normalize_relative_path
from pyuploadx.retry import retry
from pyuploadx.state import StateStore


def _resolve_object_key(
    object_key: str | None,
    directory: str | None,
    filename: str,
) -> str:
    """Compose the storage object key.

    Explicit object_key wins; otherwise directory is normalized and joined with
    the source filename (e.g. directory="reports/2026" -> "reports/2026/README.md").
    """
    if object_key:
        return object_key
    if directory:
        return f"{normalize_relative_path(directory)}/{filename}"
    return filename


def _stream_response(response: httpx.Response, dest: Path, progress: Any = None) -> Path:
    total = int(response.headers.get("content-length") or 0)
    written = 0
    with dest.open("wb") as handle:
        for chunk in response.iter_bytes():
            handle.write(chunk)
            written += len(chunk)
            if progress is not None:
                progress(written, total)
    return dest


def _stream_to_disk(
    url: str,
    dest: Path,
    progress: Any = None,
    transport: httpx.BaseTransport | None = None,
) -> Path:
    client = httpx.Client(follow_redirects=True, timeout=60.0, transport=transport)
    try:
        with client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise UploadClientError(f"download failed with status {response.status_code}")
            return _stream_response(response, dest, progress=progress)
    finally:
        client.close()


class UploadClient:
    def __init__(
        self,
        base_url: str,
        *,
        bearer_token: str | None = None,
        api_key: str | None = None,
        state_dir: str = "~/.pyuploadx/uploads",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not bearer_token and not api_key:
            raise UploadClientError("either bearer_token or api_key is required")
        headers: dict[str, str] = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
            transport=transport,
        )
        self.state = StateStore(state_dir)
        self._upload_progress: Any = None

    def on_progress(self, callback: Any) -> None:
        self._upload_progress = callback

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        payload = response.json()
        error = payload.get("error", {})
        code = error.get("code", "")
        message = error.get("message", response.text)
        exc_class = ERROR_MAP.get(code, UploadClientError)
        exc = exc_class(message)
        exc.status_code = response.status_code  # type: ignore[attr-defined]
        raise exc

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        def guarded() -> httpx.Response:
            response = self._client.request(method, path, **kwargs)
            if response.status_code in (408, 429, 500, 502, 503, 504):
                from pyuploadx.exceptions import ServerError

                exc = ServerError(f"server returned {response.status_code}")
                exc.status_code = response.status_code  # type: ignore[attr-defined]
                raise exc
            return response

        return retry(guarded)

    def upload_file(
        self,
        file_path: str,
        *,
        bucket: str,
        object_key: str | None = None,
        directory: str | None = None,
        lifecycle: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> FileInfo:
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise UploadClientError(f"file not found: {path}")
        resolved_key = _resolve_object_key(object_key, directory, path.name)
        fingerprint = fast_fingerprint(path)
        import json

        data: dict[str, str] = {"bucket": bucket, "object_key": resolved_key}
        data["file_fingerprint"] = fingerprint
        if lifecycle is not None:
            data["lifecycle"] = json.dumps(
                lifecycle.to_dict() if hasattr(lifecycle, "to_dict") else lifecycle
            )
        if metadata:
            data["metadata"] = json.dumps(metadata)
        with path.open("rb") as file:
            files = {"file": (path.name, file, "application/octet-stream")}
            response = retry(lambda: self._client.post("/v1/files/upload", files=files, data=data))
        self._raise_for_status(response)
        return FileInfo.from_dict(response.json())

    def upload_large_file(
        self,
        file_path: str,
        *,
        bucket: str,
        object_key: str | None = None,
        directory: str | None = None,
        part_size: int = 8 * 1024 * 1024,
        concurrency: int = 4,
        resume: bool = True,
        lifecycle: Any = None,
    ) -> FileInfo:
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise UploadClientError(f"file not found: {path}")
        total_size = path.stat().st_size
        fingerprint = fast_fingerprint(path)
        resolved_key = _resolve_object_key(object_key, directory, path.name)
        lifecycle_payload = lifecycle.to_dict() if lifecycle is not None else None

        session = self.create_upload(
            bucket=bucket,
            object_key=resolved_key,
            total_size=total_size,
            part_size=part_size,
            file_fingerprint=fingerprint,
            lifecycle=lifecycle_payload,
        )

        local_state = self.state.load(session.id)
        if resume and local_state and local_state.fingerprint != fingerprint:
            local_state = None
        if resume and local_state:
            resume_data = self._request("POST", f"/v1/uploads/{session.id}/resume").json()
            missing = set(resume_data.get("missing_parts", []))
        else:
            missing = set(range(1, session.total_parts + 1))

        upload_all_parts(
            http_post=lambda p, **kw: self._request("PUT", p, **kw),
            session=session,
            file_path=path,
            part_size=session.part_size,
            total_parts=session.total_parts,
            concurrency=concurrency,
            progress=self._upload_progress,
            missing_parts=missing,
        )

        response = retry(lambda: self._request("POST", f"/v1/uploads/{session.id}/complete"))
        self._raise_for_status(response)
        file_info = FileInfo.from_dict(response.json())
        self.state.delete(session.id)
        return file_info

    def create_upload(
        self,
        *,
        bucket: str,
        object_key: str,
        total_size: int,
        part_size: int,
        file_fingerprint: str | None = None,
        expected_sha256: str | None = None,
        lifecycle: dict[str, Any] | None = None,
    ) -> UploadSessionInfo:
        body: dict[str, Any] = {
            "bucket": bucket,
            "object_key": object_key,
            "total_size": total_size,
            "part_size": part_size,
            "upload_mode": "automatic",
        }
        if file_fingerprint:
            body["file_fingerprint"] = file_fingerprint
        if expected_sha256:
            body["expected_sha256"] = expected_sha256
        if lifecycle:
            body["lifecycle"] = lifecycle
        response = self._request("POST", "/v1/uploads", json=body)
        self._raise_for_status(response)
        return UploadSessionInfo.from_dict(response.json())

    def upload_directory(
        self,
        directory_path: str,
        *,
        bucket: str,
        destination_prefix: str = "",
        recursive: bool = True,
        resume: bool = True,
        file_concurrency: int = 8,
        part_concurrency: int = 4,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        symlink_policy: str = "ignore",
        conflict_policy: str = "reject",
        lifecycle: Any = None,
    ) -> DirectoryJobInfo:
        root = Path(directory_path).expanduser()
        if not root.is_dir():
            raise UploadClientError(f"directory not found: {root}")
        files, directories = walk_directory(
            root,
            recursive=recursive,
            include=include,
            exclude=exclude,
            symlink_policy=symlink_policy,
        )
        lifecycle_payload = lifecycle.to_dict() if lifecycle is not None else None
        job_response = self._request(
            "POST",
            "/v1/directory-uploads",
            json={
                "root_directory_name": root.name,
                "bucket": bucket,
                "destination_prefix": destination_prefix,
                "conflict_policy": conflict_policy,
                "source": "sdk",
                "lifecycle": lifecycle_payload,
            },
        )
        self._raise_for_status(job_response)
        job = DirectoryJobInfo.from_dict(job_response.json())
        job_id = job.id

        state_path = self.state.directories_root / f"{job_id}.sqlite3"
        db_state = DirectoryState(state_path)
        try:
            all_entries = directories + files
            for batch_start in range(0, len(all_entries), 500):
                batch = all_entries[batch_start : batch_start + 500]
                response = self._request(
                    "POST", f"/v1/directory-uploads/{job_id}/entries", json={"entries": batch}
                )
                self._raise_for_status(response)
            for entry in all_entries:
                db_state.upsert_entry(
                    entry["relative_path"], entry["entry_type"], entry.get("size_bytes", 0)
                )

            manifest_hash = manifest_hash_from_entries(files)
            response = self._request(
                "POST",
                f"/v1/directory-uploads/{job_id}/manifest/complete",
                json={
                    "manifest_hash": manifest_hash,
                    "counts": {
                        "files": len(files),
                        "directories": len(directories),
                    },
                },
            )
            self._raise_for_status(response)
            job = DirectoryJobInfo.from_dict(response.json())

            # Transition ready -> uploading before uploading entries (docs 13.5).
            response = self._request("POST", f"/v1/directory-uploads/{job_id}/retry")
            self._raise_for_status(response)

            # Map relative paths to server entry ids for result reporting.
            entry_ids: dict[str, str] = {}
            cursor = None
            while True:
                params = {"limit": 1000}
                if cursor:
                    params["cursor"] = cursor
                entries_response = self._request(
                    "GET", f"/v1/directory-uploads/{job_id}/entries", params=params
                )
                self._raise_for_status(entries_response)
                entries_payload = entries_response.json()
                for row in entries_payload.get("entries", []):
                    entry_ids[row["relative_path"]] = row["id"]
                cursor = entries_payload.get("next_cursor")
                if not cursor:
                    break

            for entry in files:
                entry_path = root / entry["relative_path"]
                try:
                    file_info = self.upload_file(
                        str(entry_path),
                        bucket=bucket,
                        object_key=f"{destination_prefix}/{entry['relative_path']}".strip("/"),
                        lifecycle=lifecycle,
                    )
                    db_state.mark_uploaded(entry["relative_path"], "", file_info.id)
                    self._request(
                        "POST",
                        f"/v1/directory-uploads/{job_id}/entries/result",
                        json={
                            "entry_id": entry_ids.get(entry["relative_path"], ""),
                            "status": "uploaded",
                            "file_id": file_info.id,
                        },
                    )
                except UploadClientError:
                    self._request(
                        "POST",
                        f"/v1/directory-uploads/{job_id}/entries/result",
                        json={
                            "entry_id": entry_ids.get(entry["relative_path"], ""),
                            "status": "failed",
                            "error_code": "UPLOAD_FAILED",
                            "error_message": "entry upload failed",
                        },
                    )
            response = self._request("POST", f"/v1/directory-uploads/{job_id}/complete")
            self._raise_for_status(response)
            return DirectoryJobInfo.from_dict(response.json())
        finally:
            db_state.close()

    def download(
        self,
        file_id: str,
        destination: str,
        *,
        url: str | None = None,
        progress: Any = None,
    ) -> Path:
        """Download a file to disk, streaming in chunks (no full buffering).

        Default streams through the API proxy (GET /v1/files/{id}/download).
        Pass url= to stream from an HTTP(S) URL directly (presigned or
        permanent link) without any presign lookup or backend probing.
        progress(bytes_written, total_bytes) is invoked per chunk when provided.
        """
        dest = Path(destination).expanduser()
        if url is not None:
            return _stream_to_disk(url, dest, progress=progress)
        with self._client.stream("GET", f"/v1/files/{file_id}/download") as response:
            self._raise_for_status(response)
            return _stream_response(response, dest, progress=progress)

    def download_from_url(
        self,
        url: str,
        destination: str,
        *,
        progress: Any = None,
    ) -> Path:
        """Stream any HTTP(S) URL (presigned or permanent link) to disk.

        Equivalent to download(file_id, url=url) when the URL is already known;
        no file_id or backend capability lookup is involved.
        """
        dest = Path(destination).expanduser()
        return _stream_to_disk(url, dest, progress=progress)

    def delete(self, file_id: str) -> None:
        response = self._request("DELETE", f"/v1/files/{file_id}")
        self._raise_for_status(response)

    def get_file(self, file_id: str) -> FileInfo:
        response = self._request("GET", f"/v1/files/{file_id}")
        self._raise_for_status(response)
        return FileInfo.from_dict(response.json())

    def get_upload(self, upload_id: str) -> UploadSessionInfo:
        response = self._request("GET", f"/v1/uploads/{upload_id}")
        self._raise_for_status(response)
        return UploadSessionInfo.from_dict(response.json())

    def get_directory_job(self, job_id: str) -> DirectoryJobInfo:
        response = self._request("GET", f"/v1/directory-uploads/{job_id}")
        self._raise_for_status(response)
        return DirectoryJobInfo.from_dict(response.json())

    def get_download_url(
        self,
        file_id: str,
        expires_seconds: int | None = None,
    ) -> str | None:
        """Return a fresh presigned download URL, or None on backends without
        presigned_get (e.g. Local) where downloads must proxy through the API.
        """
        body: dict[str, Any] = {}
        if expires_seconds is not None:
            body["expires_seconds"] = expires_seconds
        try:
            response = self._request("POST", f"/v1/files/{file_id}/presign-download", json=body)
            self._raise_for_status(response)
            return response.json().get("url")
        except UploadClientError as exc:
            if getattr(exc, "status_code", None) == 501:
                return None
            raise

    def get_lifecycle(self, file_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/v1/files/{file_id}/lifecycle")
        self._raise_for_status(response)
        return response.json()

    def update_lifecycle(self, file_id: str, lifecycle: dict[str, Any]) -> dict[str, Any]:
        response = self._request("PATCH", f"/v1/files/{file_id}/lifecycle", json=lifecycle)
        self._raise_for_status(response)
        return response.json()

    def extend_lifecycle(self, file_id: str, extend_seconds: int) -> dict[str, Any]:
        response = self._request(
            "POST", f"/v1/files/{file_id}/lifecycle/extend", json={"extend_seconds": extend_seconds}
        )
        self._raise_for_status(response)
        return response.json()

    def set_legal_hold(self, file_id: str, hold: bool = True) -> dict[str, Any]:
        if hold:
            response = self._request("POST", f"/v1/files/{file_id}/legal-hold")
        else:
            response = self._request("DELETE", f"/v1/files/{file_id}/legal-hold")
        self._raise_for_status(response)
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> UploadClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
