"""State machine tests (docs 12.1, 13.5, 14.2)."""

from __future__ import annotations

import pytest

from app.core.errors import UploadStateConflictError
from app.db.models import DirectoryJobStatus, LifecycleStatus, UploadStatus
from app.directory_upload.state_machine import transition as transition_directory
from app.lifecycle.state_machine import transition_lifecycle, transition_upload


def test_upload_state_machine_happy_path():
    status = UploadStatus.initiated
    status = transition_upload(status, UploadStatus.uploading)
    status = transition_upload(status, UploadStatus.completing)
    status = transition_upload(status, UploadStatus.completed)
    assert status == UploadStatus.completed


def test_upload_state_machine_recoverable_completing_to_uploading():
    assert transition_upload(UploadStatus.completing, UploadStatus.uploading) == UploadStatus.uploading


def test_upload_state_machine_rejects_invalid_transition():
    with pytest.raises(UploadStateConflictError):
        transition_upload(UploadStatus.completed, UploadStatus.uploading)


def test_directory_state_machine():
    status = DirectoryJobStatus.created
    status = transition_directory(status, DirectoryJobStatus.manifest_uploading)
    status = transition_directory(status, DirectoryJobStatus.ready)
    status = transition_directory(status, DirectoryJobStatus.uploading)
    status = transition_directory(status, DirectoryJobStatus.finalizing)
    status = transition_directory(status, DirectoryJobStatus.completed)
    assert status == DirectoryJobStatus.completed


def test_lifecycle_state_machine():
    assert transition_lifecycle(LifecycleStatus.active, LifecycleStatus.expiring) == LifecycleStatus.expiring
    assert transition_lifecycle(LifecycleStatus.archived, LifecycleStatus.restoring) == LifecycleStatus.restoring
