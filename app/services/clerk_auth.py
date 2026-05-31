"""Verify Clerk session JWTs (RS256) against the instance JWKS.

The Clerk Frontend API / issuer is encoded in the publishable key:
  pk_test_<base64("<frontend-api>$")>  ->  issuer = https://<frontend-api>
"""
from __future__ import annotations

import base64
from functools import lru_cache
from typing import Optional

import jwt
from jwt import PyJWKClient

from app.core.config import settings


@lru_cache(maxsize=1)
def _issuer() -> Optional[str]:
    pk = settings.clerk_publishable_key
    if not pk:
        return None
    try:
        b64 = pk.split("_", 2)[2]  # strip pk_test_ / pk_live_
        decoded = base64.b64decode(b64 + "==").decode()  # pad generously
        host = decoded.rstrip("$").strip()
        return f"https://{host}"
    except Exception:
        return None


@lru_cache(maxsize=1)
def _jwks_client() -> Optional[PyJWKClient]:
    iss = _issuer()
    return PyJWKClient(f"{iss}/.well-known/jwks.json") if iss else None


def org_from_claims(claims: dict) -> tuple[Optional[str], Optional[str]]:
    """Extract (org_id, org_role) from Clerk session claims across token shapes.

    Newer tokens use a compact `o` object {id, rol, slg}; older ones use flat
    `org_id` / `org_role`. Role normalized to include the `org:` prefix.
    """
    org_id = claims.get("org_id")
    org_role = claims.get("org_role")
    o = claims.get("o")
    if isinstance(o, dict):
        org_id = org_id or o.get("id")
        org_role = org_role or o.get("rol")
    if org_role and not org_role.startswith("org:"):
        org_role = f"org:{org_role}"  # compact tokens drop the prefix (e.g. "admin")
    return org_id, org_role


def verify_clerk_token(token: str) -> Optional[dict]:
    """Return the verified claims, or None if invalid / Clerk not configured."""
    iss = _issuer()
    client = _jwks_client()
    if not iss or not client:
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=iss,
            options={"verify_aud": False},
            leeway=30,
        )
    except Exception:
        return None
