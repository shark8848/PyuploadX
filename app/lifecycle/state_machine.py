"""Upload and lifecycle state machines per docs sections 12.1 and 14.2."""

from __future__ import annotations

from app.core.errors import UploadStateConflictError
from app.db.models import LifecycleStatus, UploadStatus

UPLOAD_TRANSITIONS: dict[UploadStatus, set[UploadStatus]] = {
    UploadStatus.initiated: {UploadStatus.uploading, UploadStatus.aborting, UploadStatus.expired},
    UploadStatus.uploading: {
        UploadStatus.completing,
        UploadStatus.aborting,
        UploadStatus.expired,
    },
    UploadStatus.completing: {UploadStatus.completed, UploadStatus.uploading},
    UploadStatus.aborting: {UploadStatus.aborted},
}


def transition_upload(current: UploadStatus, target: UploadStatus) -> UploadStatus:
    allowed = UPLOAD_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise UploadStateConflictError(
            f"Cannot transition upload from {current.value} to {target.value}."
        )
    return target


LIFECYCLE_TRANSITIONS: dict[LifecycleStatus, set[LifecycleStatus]] = {
    LifecycleStatus.active: {
        LifecycleStatus.expiring,
        LifecycleStatus.archiving,
        LifecycleStatus.deleting,
        LifecycleStatus.deleted,
    },
    LifecycleStatus.expiring: {LifecycleStatus.expired, LifecycleStatus.deleting},
    LifecycleStatus.expired: {LifecycleStatus.deleting, LifecycleStatus.deleted},
    LifecycleStatus.deleting: {LifecycleStatus.deleted},
    LifecycleStatus.archiving: {LifecycleStatus.archived},
    LifecycleStatus.archived: {LifecycleStatus.restoring},
    LifecycleStatus.restoring: {LifecycleStatus.active},
}


def transition_lifecycle(current: LifecycleStatus, target: LifecycleStatus) -> LifecycleStatus:
    allowed = LIFECYCLE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise UploadStateConflictError(
            f"Cannot transition lifecycle from {current.value} to {target.value}."
        )
    return target
