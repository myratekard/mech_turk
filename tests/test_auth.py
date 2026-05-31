from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services import auth
from app.api.deps import require_roles


def test_password_hash_roundtrip():
    h = auth.hash_password("s3cret!")
    assert h.startswith("pbkdf2_sha256$")
    assert auth.verify_password("s3cret!", h)
    assert not auth.verify_password("wrong", h)


def test_token_roundtrip():
    tok = auth.create_access_token(7, "admin", "alice")
    payload = auth.decode_token(tok)
    assert payload is not None
    assert payload["sub"] == "7"
    assert payload["role"] == "admin"
    assert payload["username"] == "alice"


def test_decode_garbage_returns_none():
    assert auth.decode_token("not-a-jwt") is None


def test_require_roles_allows_and_denies():
    dep = require_roles("superuser", "admin")
    assert dep(user={"role": "admin"})["role"] == "admin"
    with pytest.raises(HTTPException) as exc:
        dep(user={"role": "user"})
    assert exc.value.status_code == 403
