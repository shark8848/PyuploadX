"""Bucket management API (create/list user buckets)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import IdentityDep, SessionDep, StateDep

router = APIRouter(prefix="/buckets", tags=["buckets"])


@router.get("")
async def list_buckets(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
) -> dict[str, Any]:
    buckets = await state.bucket_service.list_buckets_for_tenant(db, identity.tenant_id)
    return {"buckets": buckets}


@router.post("", status_code=201)
async def create_bucket(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    body: dict[str, Any],
) -> dict[str, Any]:
    name = body.get("name") if isinstance(body, dict) else None
    bucket = await state.bucket_service.create_bucket(db, identity, name)
    await db.commit()
    return bucket


@router.delete("/{name}")
async def delete_bucket(
    name: str,
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
) -> dict[str, Any]:
    result = await state.bucket_service.delete_bucket(db, identity, name)
    await db.commit()
    return result
