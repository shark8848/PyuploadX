"""Directory upload API per docs_product-design.md section 16.6."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.dependencies import IdentityDep, SessionDep, StateDep
from app.core.errors import ApiError
from app.directory_upload.manifest import parse_manifest_ndjson, serialize_manifest_ndjson
from app.services.directory_upload_service import (
    serialize_entry,
    serialize_job,
)


router = APIRouter(prefix="/directory-uploads", tags=["directory-uploads"])


@router.post("")
async def create_directory_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    body: dict[str, Any],
) -> dict[str, Any]:
    job = await state.directory_service.create_job(
        db,
        identity,
        root_directory_name=body.get("root_directory_name", ""),
        bucket=body.get("bucket") or state.settings.storage.default_bucket,
        destination_prefix=body.get("destination_prefix", ""),
        conflict_policy=body.get("conflict_policy", "reject"),
        source=body.get("source", "sdk"),
        requested_lifecycle=body.get("lifecycle"),
    )
    await db.commit()
    return serialize_job(job)


@router.post("/{job_id}/entries")
async def add_entries(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    entries = body.get("entries") or []
    added = await state.directory_service.add_entries(db, identity, job_id, entries)
    await db.commit()
    return {"added": added}


@router.post("/{job_id}/entries/stream")
async def stream_entries(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    payload = await request.body()
    entries = parse_manifest_ndjson(payload.decode("utf-8"))
    added = await state.directory_service.add_entries(db, identity, job_id, entries)
    await db.commit()
    return {"added": added}


@router.post("/{job_id}/manifest/complete")
async def complete_manifest(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    job = await state.directory_service.complete_manifest(
        db,
        identity,
        job_id,
        expected_hash=body.get("manifest_hash"),
        counts=body.get("counts"),
    )
    await db.commit()
    return job


@router.get("/{job_id}")
async def get_directory_upload(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
) -> dict[str, Any]:
    job = await state.directory_service.get_job(db, identity, job_id)
    return serialize_job(job)


@router.get("/{job_id}/entries")
async def get_entries(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    rows, next_cursor = await state.directory_service.list_entries(
        db, identity, job_id, cursor=cursor, limit=limit
    )
    return {
        "entries": [serialize_entry(row) for row in rows],
        "next_cursor": next_cursor,
    }


@router.get("/{job_id}/manifest")
async def get_manifest(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
) -> dict[str, Any]:
    rows, _ = await state.directory_service.list_entries(db, identity, job_id, cursor=None, limit=100000)
    entries = [
        {
            "entry_type": row.entry_type.value,
            "relative_path": row.relative_path,
            "size_bytes": row.size_bytes,
            "fingerprint": row.fingerprint,
            "last_modified_ns": row.last_modified_ns,
        }
        for row in rows
    ]
    return {
        "content_type": "application/x-ndjson",
        "manifest": serialize_manifest_ndjson(entries),
    }


@router.post("/{job_id}/entries/initiate")
async def initiate_entry(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    result = await state.directory_service.initiate_entry(
        db, identity, job_id, uuid.UUID(body["entry_id"])
    )
    await db.commit()
    return result


@router.post("/{job_id}/entries/result")
async def mark_entry_result(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    from app.db.models import EntryStatus

    result = await state.directory_service.mark_entry_result(
        db,
        identity,
        job_id,
        uuid.UUID(body["entry_id"]),
        status=EntryStatus(body.get("status", "uploaded")),
        file_id=uuid.UUID(body["file_id"]) if body.get("file_id") else None,
        error_code=body.get("error_code"),
        error_message=body.get("error_message"),
    )
    await db.commit()
    return result


@router.post("/{job_id}/retry")
async def retry_job(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
) -> dict[str, Any]:
    job = await state.directory_service.retry(db, identity, job_id)
    await db.commit()
    return job


@router.post("/{job_id}/complete")
async def complete_job(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
) -> dict[str, Any]:
    job = await state.directory_service.complete(db, identity, job_id)
    await db.commit()
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
) -> dict[str, Any]:
    job = await state.directory_service.cancel(db, identity, job_id)
    await db.commit()
    return job


@router.patch("/{job_id}/lifecycle")
async def patch_job_lifecycle(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    job_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    job = await state.directory_service.get_job(db, identity, job_id)
    from app.lifecycle.policy import compute_effective_lifecycle

    effective = compute_effective_lifecycle(
        requested=body,
        server_default=state.settings.lifecycle.default_policy.model_dump(),
        allow_client_override=state.settings.lifecycle.policy.allow_client_override,
        permanent_allowed=state.settings.lifecycle.policy.permanent_allowed,
        minimum_ttl_seconds=state.settings.lifecycle.policy.minimum_ttl_seconds,
        maximum_ttl_seconds=state.settings.lifecycle.policy.maximum_ttl_seconds,
        allowed_modes=state.settings.lifecycle.policy.allowed_modes,
        allowed_actions=state.settings.lifecycle.policy.allowed_actions,
    )
    job.requested_lifecycle = body
    job.effective_lifecycle = effective
    await db.commit()
    return serialize_job(job)
