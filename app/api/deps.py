"""Auth dependencies: extract+verify the bearer token, load the user, gate by role."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.services import auth_db
from app.services.clerk_auth import org_from_claims, verify_clerk_token

_ORG_ROLE_MAP = {"org:admin": "admin", "org:member": "user"}


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Authenticate via a Clerk session token; merge our DB mirror with Clerk org claims.

    Org + org-role come from the Clerk session (source of truth); 'superuser' is our
    app-level flag in the DB mirror. The local user is provisioned by /api/auth/clerk/sync.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    claims = verify_clerk_token(token)
    if not claims or not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = auth_db.get_user_by_clerk_id(claims["sub"])
    if not user:
        raise HTTPException(status_code=409, detail="Account not provisioned; sync required")
    if user.get("blocked"):
        raise HTTPException(status_code=403, detail="This account has been blocked")

    org_id, org_role = org_from_claims(claims)
    # Effective role: app-level flags (superuser, turk_admin) win; otherwise derive
    # from the Clerk org role (org:admin -> admin, org:member -> user).
    db_role = user.get("role")
    if db_role in ("superuser", "turk_admin"):
        effective_role = db_role
    else:
        effective_role = _ORG_ROLE_MAP.get(org_role or "", "user")

    # Lazily mirror the active org + role so analytics/listing/referral-validation work.
    if org_id and (user.get("clerk_org_id") != org_id or user.get("clerk_org_role") != org_role):
        auth_db.set_user_clerk_org(user["id"], org_id, org_role)
        user["clerk_org_id"] = org_id
        user["clerk_org_role"] = org_role

    user = {**user, "role": effective_role, "org_id": org_id}
    return user


def require_roles(*roles: str):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _dep


def require_superuser(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "superuser":
        raise HTTPException(status_code=403, detail="Superuser only")
    return user
