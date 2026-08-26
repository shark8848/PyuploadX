"""Lifecycle policy adjudication tests (docs section 14)."""

from __future__ import annotations

import pytest

from app.core.errors import InvalidLifecyclePolicyError, TtlOutOfRangeError
from app.lifecycle.policy import compute_effective_lifecycle

BASE = {
    "server_default": {"mode": "ttl", "ttl_seconds": 2_592_000, "action": "delete"},
    "allow_client_override": True,
    "permanent_allowed": True,
    "minimum_ttl_seconds": 3600,
    "maximum_ttl_seconds": 31_536_000,
    "allowed_modes": ["temporary", "ttl", "expires_at", "permanent", "sliding_ttl"],
    "allowed_actions": ["delete", "notify", "none"],
}


def test_server_default_applied_when_no_request():
    effective = compute_effective_lifecycle(requested=None, **BASE)
    assert effective["mode"] == "ttl"
    assert effective["ttl_seconds"] == 2_592_000
    assert effective["expires_at"] is not None


def test_client_override():
    effective = compute_effective_lifecycle(
        requested={"mode": "ttl", "ttl_seconds": 7200}, **BASE
    )
    assert effective["ttl_seconds"] == 7200


def test_client_override_disabled():
    params = dict(BASE, allow_client_override=False)
    effective = compute_effective_lifecycle(requested={"mode": "ttl", "ttl_seconds": 7200}, **params)
    assert effective["ttl_seconds"] == 2_592_000


def test_ttl_below_minimum_rejected():
    with pytest.raises(TtlOutOfRangeError):
        compute_effective_lifecycle(
            requested={"mode": "ttl", "ttl_seconds": 60}, **BASE
        )


def test_permanent_rejected_when_disallowed():
    params = dict(BASE, permanent_allowed=False)
    with pytest.raises(InvalidLifecyclePolicyError):
        compute_effective_lifecycle(requested={"mode": "permanent"}, **params)


def test_invalid_mode_rejected():
    with pytest.raises(InvalidLifecyclePolicyError):
        compute_effective_lifecycle(requested={"mode": "bogus"}, **BASE)
