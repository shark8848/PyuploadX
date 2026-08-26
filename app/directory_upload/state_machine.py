"""Directory upload job state machine per docs_product-design.md section 13.5."""

from __future__ import annotations

from app.core.errors import UploadStateConflictError
from app.db.models import DirectoryJobStatus


TRANSITIONS: dict[DirectoryJobStatus, set[DirectoryJobStatus]] = {
    DirectoryJobStatus.created: {DirectoryJobStatus.manifest_uploading, DirectoryJobStatus.cancelling},
    DirectoryJobStatus.manifest_uploading: {
        DirectoryJobStatus.ready,
        DirectoryJobStatus.cancelling,
    },
    DirectoryJobStatus.ready: {
        DirectoryJobStatus.uploading,
        DirectoryJobStatus.cancelling,
        DirectoryJobStatus.completed,
    },
    DirectoryJobStatus.uploading: {
        DirectoryJobStatus.paused,
        DirectoryJobStatus.finalizing,
        DirectoryJobStatus.cancelling,
    },
    DirectoryJobStatus.paused: {DirectoryJobStatus.uploading},
    DirectoryJobStatus.finalizing: {
        DirectoryJobStatus.completed,
        DirectoryJobStatus.completed_with_errors,
    },
    DirectoryJobStatus.cancelling: {DirectoryJobStatus.cancelled},
}


def transition(current: DirectoryJobStatus, target: DirectoryJobStatus) -> DirectoryJobStatus:
    allowed = TRANSITIONS.get(current, set())
    if target not in allowed:
        raise UploadStateConflictError(
            f"Cannot transition directory job from {current.value} to {target.value}."
        )
    return target
