"""HMAC signing for permanent download links.

Links never expire; they stay valid while the file exists. Revoke by rotating
the UPLOAD_PERMANENT_LINK_SECRET secret or by deleting the file.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid


def sign(file_id: uuid.UUID, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        str(file_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify(file_id: uuid.UUID, secret: str, token: str) -> bool:
    if not token or not secret:
        return False
    return hmac.compare_digest(sign(file_id, secret), token)
