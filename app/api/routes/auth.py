"""Auth endpoints — Clerk-backed.

Login/sign-up happen in Clerk on the frontend. The frontend calls /clerk/sync once
after sign-in to provision a local user (which holds role/org/referral). All other
endpoints authenticate via the Clerk session token (see app/api/deps.py).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.config import settings
from app.schemas.auth_models import RefInfo, UserOut
from app.services import auth_db
from app.services.clerk_auth import org_from_claims, verify_clerk_token

router = APIRouter(prefix="/auth", tags=["auth"])


class ClerkSyncInput(BaseModel):
    email: Optional[str] = None
    ref: Optional[str] = None  # referral / org registration code (optional)


def to_user_out(u: dict) -> UserOut:
    return UserOut(
        id=u["id"],
        username=u["username"],
        email=u["email"],
        role=u["role"],
        orgId=u.get("clerk_org_id"),
        referredBy=u["referred_by"],
        referralCode=u["referral_code"],
        blocked=bool(u.get("blocked", 0)),
        createdAt=u["created_at"],
    )


def _resolve_ref(code: str):
    """A valid referral code belongs to an ORG ADMIN (only admins can refer).

    Returns (inviter_id, inviter_clerk_org_id, org_name, inviter_username) or None.
    Signing up through it records referred_by and joins that admin's org as a member.
    """
    inviter = auth_db.get_user_by_referral_code(code)
    if not inviter:
        return None
    clerk_org_id = inviter.get("clerk_org_id")
    is_org_admin = (inviter.get("clerk_org_role") or "").endswith("admin")
    if not clerk_org_id or not is_org_admin:
        return None  # users (non-admins) can't refer
    org = auth_db.get_clerk_org(clerk_org_id)
    return inviter["id"], clerk_org_id, (org["name"] if org else None), inviter["username"]


@router.get("/ref/{code}", response_model=RefInfo)
def ref_info(code: str):
    resolved = _resolve_ref(code)
    if not resolved:
        return RefInfo(valid=False)
    _inviter_id, _org, org_name, inviter = resolved
    return RefInfo(valid=True, role="user", orgName=org_name, inviter=inviter)


@router.post("/clerk/sync", response_model=UserOut)
def clerk_sync(body: ClerkSyncInput, authorization: Optional[str] = Header(default=None)):
    """Provision (or fetch) the local user. Access is strictly org-tied:

      superuser (first/SUPERUSER_EMAIL) | turk_admin (superuser email invite) |
      uploader via a valid org-admin referral code | staff via a Clerk org invitation.
    Any other sign-up is rejected (no open registration).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    claims = verify_clerk_token(authorization.split(" ", 1)[1].strip())
    if not claims or not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    clerk_id = claims["sub"]
    existing = auth_db.get_user_by_clerk_id(clerk_id)
    if existing:
        return to_user_out(existing)

    email = (body.email or "").strip() or None
    org_id_claim, org_role_claim = org_from_claims(claims)
    # Superuser is determined SOLELY by SUPERUSER_EMAIL — no "first user wins" fallback,
    # which on a public URL would let a stranger claim superuser before the owner signs in.
    is_superuser = bool(
        settings.superuser_email and email and email.lower() == settings.superuser_email.lower()
    )

    role, referred_by, join_org = "user", None, None
    if is_superuser:
        role = "superuser"
    elif auth_db.is_pending_turk_admin(email):
        role = "turk_admin"
    elif body.ref:
        resolved = _resolve_ref(body.ref.strip())
        if resolved:
            referred_by, join_org = resolved[0], resolved[1]
        else:
            raise HTTPException(status_code=403, detail="Invalid or expired referral link")
    elif not org_id_claim:
        # No superuser/turk-admin/referral and not arriving via a Clerk org invitation.
        raise HTTPException(
            status_code=403,
            detail="Registration requires a valid organization invite or referral link.",
        )

    username = (email.split("@")[0] if email else None) or f"user{clerk_id[-6:]}"
    user = auth_db.create_clerk_user(
        clerk_id=clerk_id, username=username, email=email,
        role=role, org_id=None, referred_by=referred_by,
    )
    if role == "turk_admin" and email:
        auth_db.mark_turk_admin_invite_used(email)

    # Referral signup -> add to the inviter's Clerk org as a member (best-effort).
    if join_org:
        try:
            from app.services import clerk_api
            clerk_api.add_member(join_org, clerk_id, "org:member")
            auth_db.set_user_clerk_org(user["id"], join_org, "org:member")
            user["clerk_org_id"] = join_org
        except Exception as e:
            print(f"[clerk] auto-join org failed: {e}")
    elif org_id_claim:
        # Staff who accepted a Clerk org invitation — mirror their org now.
        auth_db.set_user_clerk_org(user["id"], org_id_claim, org_role_claim)
        user["clerk_org_id"] = org_id_claim

    return to_user_out(user)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return to_user_out(user)
