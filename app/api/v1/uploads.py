"""Upload session and multipart API per docs_product-design.md section 16.4."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request

from app.api.dependencies import IdentityDep, SessionDep, StateDep
from app.core.streaming import spool_request
from app.services.upload_service import serialize_session

router = APIRouter(prefix="/uploads", tags=["uploads"])

@router.post("")
async def create_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    body: dict[str, Any],
) -> dict[str, Any]:
    upload = await state.upload_service.create_session(
        db,
        identity,
        bucket=body.get("bucket") or state.settings.storage.default_bucket,
        object_key=body["object_key"],
        original_filename=body.get("original_filename", ""),
        content_type=body.get("content_type"),
        total_size=int(body.get("total_size", 0)),
        part_size=body.get("part_size"),
        upload_mode=body.get("upload_mode") or "automatic",
        file_fingerprint=body.get("file_fingerprint"),
        expected_sha256=body.get("expected_sha256"),
        lifecycle=body.get("lifecycle"),
        metadata=body.get("metadata"),
    )
    await db.commit()
    return serialize_session(upload)


@router.post("/resume")
async def resume_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    body: dict[str, Any],
) -> dict[str, Any]:
    upload_id = uuid.UUID(body["upload_id"])
    upload, missing = await state.upload_service.resume(db, identity, upload_id)
    await db.commit()
    return {
        "session": serialize_session(upload),
        "missing_parts": missing,
    }


@router.get("/{upload_id}")
async def get_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
) -> dict[str, Any]:
    upload = await state.upload_service.get_session(db, identity, upload_id)
    return serialize_session(upload)


@router.get("/{upload_id}/parts")
async def list_parts(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
) -> dict[str, Any]:
    parts = await state.upload_service.list_committed_parts(db, identity, upload_id)
    return {
        "parts": [
            {
                "part_number": part.part_number,
                "offset_bytes": part.offset_bytes,
                "size_bytes": part.size_bytes,
                "etag": part.etag,
                "checksum_sha256": part.checksum_sha256,
                "status": part.status.value,
            }
            for part in parts
        ]
    }


@router.post("/{upload_id}/parts/presign")
async def presign_parts(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    part_numbers = body.get("part_numbers") or []
    expires = body.get("expires_seconds")
    urls = await state.upload_service.presign_parts(
        db, identity, upload_id, part_numbers, expires_seconds=expires
    )
    return {
        "urls": {str(k): v for k, v in urls.items()},
        "expires_seconds": expires,
    }


@router.put("/{upload_id}/parts/{part_number}")
async def proxy_upload_part(
    request: Request,
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
    part_number: int,
) -> dict[str, Any]:
    spooled = await spool_request(request)
    try:
        checksum = request.headers.get("X-Part-SHA256")
        part = await state.upload_service.proxy_upload_part(
            db,
            identity,
            upload_id,
            part_number,
            spooled.file,
            spooled.size_bytes,
            checksum_sha256=checksum or spooled.sha256,
        )
        await db.commit()
    finally:
        spooled.close()
    return {
        "part_number": part.part_number,
        "size_bytes": part.size_bytes,
        "etag": part.etag,
        "checksum_sha256": part.checksum_sha256,
        "status": part.status.value,
    }


@router.post("/{upload_id}/parts/commit")
async def commit_part(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    await state.upload_service.commit_part(
        db,
        identity,
        upload_id,
        int(body["part_number"]),
        str(body["etag"]),
        int(body.get("size_bytes", 0)),
        body.get("checksum_sha256"),
    )
    await db.commit()
    return {"status": "committed", "part_number": body["part_number"]}


@router.post("/{upload_id}/refresh")
async def refresh_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
) -> dict[str, Any]:
    upload = await state.upload_service.refresh(db, identity, upload_id)
    await db.commit()
    return serialize_session(upload)


@router.post("/{upload_id}/complete")
async def complete_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
) -> dict[str, Any]:
    file_obj = await state.upload_service.complete(db, identity, upload_id)
    await db.commit()
    return await state.file_service.serialize_upload_result(db, identity, file_obj)


@router.post("/{upload_id}/abort")
async def abort_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    upload_id: uuid.UUID,
) -> dict[str, Any]:
    upload = await state.upload_service.abort(db, identity, upload_id)
    await db.commit()
    return serialize_session(upload)
