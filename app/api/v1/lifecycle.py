"""Lifecycle API per docs_product-design.md section 16.5."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from app.api.dependencies import IdentityDep, SessionDep, StateDep


router = APIRouter(prefix="/files", tags=["lifecycle"])


@router.get("/{file_id}/lifecycle")
async def get_lifecycle(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
) -> dict[str, Any]:
    return await state.lifecycle_service.get_lifecycle(db, identity, file_id)


@router.patch("/{file_id}/lifecycle")
async def update_lifecycle(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    result = await state.lifecycle_service.update_lifecycle(db, identity, file_id, body)
    await db.commit()
    return result


@router.post("/{file_id}/lifecycle/extend")
async def extend_lifecycle(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    result = await state.lifecycle_service.extend(
        db, identity, file_id, int(body.get("extend_seconds", 0))
    )
    await db.commit()
    return result


@router.post("/{file_id}/lifecycle/make-permanent")
async def make_permanent(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
) -> dict[str, Any]:
    result = await state.lifecycle_service.make_permanent(db, identity, file_id)
    await db.commit()
    return result


@router.post("/{file_id}/legal-hold")
async def set_legal_hold(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
) -> dict[str, Any]:
    result = await state.lifecycle_service.set_legal_hold(db, identity, file_id, True)
    await db.commit()
    return result


@router.delete("/{file_id}/legal-hold")
async def release_legal_hold(
    state: StateDep,
    db: SessionDep,
    identity: IdentityDep,
    file_id: uuid.UUID,
) -> dict[str, Any]:
    result = await state.lifecycle_service.set_legal_hold(db, identity, file_id, False)
    await db.commit()
    return result
