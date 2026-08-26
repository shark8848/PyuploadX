"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config.models import Settings
from app.core.auth import ApiKeyAuthenticator, Identity
from app.db.session import build_engine, build_session_factory
from app.services.directory_upload_service import DirectoryUploadService
from app.services.file_service import FileService
from app.services.lifecycle_service import LifecycleService
from app.services.upload_service import UploadService
from app.storage.base import StorageAdapter
from app.storage.factory import build_storage


@dataclass
class AppState:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    storage: StorageAdapter
    authenticator: ApiKeyAuthenticator
    upload_service: UploadService = field(init=False)
    file_service: FileService = field(init=False)
    lifecycle_service: LifecycleService = field(init=False)
    directory_service: DirectoryUploadService = field(init=False)

    def __post_init__(self) -> None:
        self.upload_service = UploadService(self.settings, self.storage)
        self.file_service = FileService(self.settings, self.storage)
        self.lifecycle_service = LifecycleService(self.settings)
        self.directory_service = DirectoryUploadService(self.settings)


def build_app_state(settings: Settings) -> AppState:
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    storage = build_storage(settings)
    authenticator = ApiKeyAuthenticator(settings.auth.api_key.keys_from_env)
    return AppState(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        storage=storage,
        authenticator=authenticator,
    )


def get_app_state(request: Request) -> AppState:
    return request.app.state.state


StateDep = Annotated[AppState, Depends(get_app_state)]


async def get_db_session(state: StateDep) -> AsyncIterator[AsyncSession]:
    async with state.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_identity(
    state: StateDep,
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Identity:
    if state.settings.auth.mode == "none":
        return Identity(tenant_id="default", principal_id="anonymous")
    key = x_api_key
    if not key:
        key = request.headers.get(state.settings.auth.api_key.header_name)
    return state.authenticator.authenticate(key)


IdentityDep = Annotated[Identity, Depends(get_identity)]


def request_id_header(x_request_id: Annotated[str | None, Header()] = None) -> str:
    return x_request_id or f"req-{uuid.uuid4().hex[:16]}"


RequestIdDep = Annotated[str, Depends(request_id_header)]


def require_permission(permission: str):
    """Dependency factory for coarse-grained permission checks."""

    def checker(
        state: StateDep,
        identity: IdentityDep,
        request: Request,
    ) -> Identity:
        return identity

    return checker
