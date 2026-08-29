"""File object API per docs_product-design.md section 16.2."""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.api.dependencies import IdentityDep, SessionDep, StateDep
from app.db import repositories
from app.db.models import FileStatus
from app.services.file_service import serialize_file

router = APIRouter(prefix="/files", tags=["files"])


@router.get("")
async def list_files(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    bucket: Annotated[str | None, Query()] = None,
    prefix: Annotated[str | None, Query()] = None,
    status: Annotated[FileStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[Literal["name", "created_at"], Query()] = "name",
) -> dict[str, Any]:
    items, total = await repositories.file_repository.list_files(
        db,
        tenant_id=identity.tenant_id,
        bucket=bucket,
        prefix=prefix,
        status=status if status is not None else FileStatus.active,
        limit=limit,
        offset=offset,
        order_by=sort_by,
    )
    return {
        "items": [serialize_file(item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/upload")
async def upload_file(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file: Annotated[UploadFile, File()],
    bucket: Annotated[str, Form()],
    object_key: Annotated[str | None, Form()] = None,
    original_filename: Annotated[str | None, Form()] = None,
    content_type: Annotated[str | None, Form()] = None,
    checksum_sha256: Annotated[str | None, Form()] = None,
    file_fingerprint: Annotated[str | None, Form()] = None,
    lifecycle: Annotated[str | None, Form()] = None,
    metadata: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    lifecycle_data = json.loads(lifecycle) if lifecycle else None
    metadata_data = json.loads(metadata) if metadata else {}
    if not isinstance(lifecycle_data, dict):
        lifecycle_data = None
    if not isinstance(metadata_data, dict):
        metadata_data = {}
    size = 0
    # Spool the uploaded file to disk so we never hold it entirely in memory.
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
    await file.seek(0)
    resolved_key = object_key or file.filename or "upload.bin"
    file_obj = await state.file_service.proxy_upload(
        db,
        identity,
        bucket=bucket,
        object_key=resolved_key,
        original_filename=original_filename or file.filename or resolved_key,
        content_type=content_type or file.content_type,
        size_bytes=size,
        stream=file.file,
        checksum_sha256=checksum_sha256,
        file_fingerprint=file_fingerprint,
        lifecycle=lifecycle_data,
        metadata=metadata_data,
    )
    await db.commit()
    return await state.file_service.serialize_upload_result(db, identity, file_obj)


@router.post("/{file_id}/permanent-link")
async def create_permanent_link(
    request: Request,
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
) -> dict[str, Any]:
    url = await state.file_service.create_permanent_link(
        db, identity, file_id, str(request.base_url)
    )
    return {"url": url, "permanent": True}


@router.get("/{file_id}/download-link")
async def download_link(
    state: StateDep,
    db: SessionDep,
    file_id: uuid.UUID,
    token: str,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    if not state.file_service.verify_link_token(file_id, token):
        from app.core.errors import ApiError

        raise ApiError("INVALID_DOWNLOAD_LINK", "Invalid or missing download link token.", status_code=403)
    file_obj, stream, byte_range = await state.file_service.download_for_link(
        db, file_id, range_header=range_header
    )

    async def iterator():
        async for chunk in stream:
            yield chunk

    headers = {"X-Request-ID": "link", "Accept-Ranges": "bytes"}
    if file_obj.etag:
        headers["ETag"] = file_obj.etag
    if byte_range is not None:
        headers["Content-Range"] = f"bytes {byte_range.start}-{byte_range.end}/{file_obj.size_bytes}"
        return StreamingResponse(
            iterator(),
            status_code=206,
            media_type=file_obj.content_type or "application/octet-stream",
            headers=headers,
        )
    return StreamingResponse(
        iterator(),
        media_type=file_obj.content_type or "application/octet-stream",
        headers=headers,
    )


@router.get("/{file_id}")
async def get_file(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
) -> dict[str, Any]:
    file_obj = await state.file_service.get(db, identity, file_id)
    from app.services.file_service import serialize_file

    return serialize_file(file_obj)


@router.get("/{file_id}/download")
async def download_file(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    file_obj, stream, byte_range = await state.file_service.download(
        db, identity, file_id, range_header=range_header
    )

    async def iterator():
        async for chunk in stream:
            yield chunk

    headers = {"X-Request-ID": "stream", "Accept-Ranges": "bytes"}
    if file_obj.etag:
        headers["ETag"] = file_obj.etag
    if byte_range is not None:
        headers["Content-Range"] = f"bytes {byte_range.start}-{byte_range.end}/{file_obj.size_bytes}"
        return StreamingResponse(
            iterator(),
            status_code=206,
            media_type=file_obj.content_type or "application/octet-stream",
            headers=headers,
        )
    return StreamingResponse(
        iterator(),
        media_type=file_obj.content_type or "application/octet-stream",
        headers=headers,
    )


@router.post("/{file_id}/presign-download")
async def presign_download(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expires = (body or {}).get("expires_seconds")
    url = await state.file_service.presign_download(db, identity, file_id, expires)
    return {"url": url}


@router.delete("/{file_id}")
async def delete_file(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
) -> dict[str, Any]:
    await state.file_service.delete(db, identity, file_id)
    await db.commit()
    return {"status": "deleted", "id": str(file_id)}
