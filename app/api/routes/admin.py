"""Admin endpoints: review queue (approve/reject/rerun) + orgs/users/invites.

Review pool is GLOBAL: any superuser/admin reviews all in_review submissions.
Org/user management is superuser-wide; admins are scoped to their own org.
"""
from __future__ import annotations

import json
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, require_roles, require_superuser
from app.api.routes.auth import to_user_out
from app.api.routes.turk import map_status_points, platform_label
from app.core.config import settings
from app.schemas.auth_models import (
    CreateOrgInput,
    OrgAnalytics,
    OrgOut,
    ReviewItem,
    ReviewQueue,
    UserOut,
    UserStat,
)
from app.services import auth_db, clerk_api, storage, submissions_db
from app.services.pipeline import analyze as run_pipeline

router = APIRouter(prefix="/admin", tags=["admin"])

_reviewer = require_roles("superuser", "turk_admin")          # review queue
_analytics_roles = require_roles("superuser", "turk_admin", "admin")
_staff_roles = require_roles("superuser", "admin")            # org-scoped staff mgmt


def _to_org_out(clerk_org_id: str, name: str, created_at: str | None = None,
                email_sent: bool | None = None) -> OrgOut:
    return OrgOut(id=clerk_org_id, name=name, createdAt=created_at, emailSent=email_sent)


def _row_to_review_item(row: dict) -> ReviewItem:
    a = {}
    if row.get("analysis_json"):
        try:
            a = json.loads(row["analysis_json"])
        except Exception:
            a = {}
    ver = a.get("verification") or {}
    return ReviewItem(
        id=row["id"], userId=row["user_id"], imageUrl=row["image_url"], platform=row["platform"],
        fileName=row["file_name"], status=row["status"], createdAt=row["created_at"],
        verified=ver.get("verified"), confidence=ver.get("confidence"),
        needsReview=ver.get("needs_review"), profile=a.get("profile"),
        reasoning=(ver.get("llm_signal") or {}).get("reasoning"),
    )


# ----------------------------------------------------------------- review queue
@router.get("/review-queue", response_model=ReviewQueue)
def review_queue(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: dict = Depends(_reviewer),
):
    rows, total = submissions_db.list_review_queue(page, limit)
    return ReviewQueue(items=[_row_to_review_item(r) for r in rows], total=total, page=page, limit=limit)


@router.post("/submissions/{submission_id}/approve")
def approve(submission_id: int, user: dict = Depends(_reviewer)):
    row = submissions_db.get_submission_any(submission_id)
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    # Approving a duplicate of an already-captured account still earns no points.
    if submissions_db.is_duplicate_capture(row["acct_platform"], row["acct_handle"], exclude_id=submission_id):
        updated = submissions_db.update_submission_status(submission_id, "duplicate", 0)
        return {"ok": True, "id": submission_id, "status": "duplicate", "points": 0}
    submissions_db.update_submission_status(submission_id, "accepted", settings.points_accepted)
    return {"ok": True, "id": submission_id, "status": "accepted", "points": settings.points_accepted}


@router.post("/submissions/{submission_id}/reject")
def reject(submission_id: int, user: dict = Depends(_reviewer)):
    row = submissions_db.update_submission_status(submission_id, "invalid", 0)
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"ok": True, "id": submission_id, "status": "invalid", "points": 0}


@router.post("/submissions/{submission_id}/rerun")
def rerun(submission_id: int, user: dict = Depends(_reviewer)):
    row = submissions_db.get_submission_any(submission_id)
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    data = storage.read_object(row["object_path"])
    if data is None:
        raise HTTPException(status_code=400, detail="Stored image not found")
    mime, _ = mimetypes.guess_type(row["file_name"] or row["object_path"])
    result = run_pipeline(data, mime=mime or "image/jpeg", persist=False)
    status, points = map_status_points(result)
    acct_platform = result.platform if result.platform != "unknown" else None
    acct_handle = submissions_db.normalize_handle(getattr(result.profile, "handle", None))
    if status == "accepted" and submissions_db.is_duplicate_capture(acct_platform, acct_handle, exclude_id=submission_id):
        status, points = "duplicate", 0
    submissions_db.update_submission_status(
        submission_id, status, points, analysis_json=result.model_dump_json(),
        acct_platform=acct_platform, acct_handle=acct_handle, update_acct=True,
    )
    return {"ok": True, "id": submission_id, "status": status, "points": points,
            "platform": platform_label(result)}


# --------------------------------------------------------------- organizations
@router.post("/orgs", response_model=OrgOut)
def create_org(body: CreateOrgInput, user: dict = Depends(require_superuser)):
    # Org lives in Clerk; Clerk emails the admin invitation (org:admin).
    try:
        org = clerk_api.create_organization(body.name, created_by_clerk_id=user["clerk_id"])
        org_id = org["id"]
        auth_db.upsert_clerk_org(org_id, body.name)
        email_sent = None
        if body.adminEmail:
            clerk_api.create_organization_invitation(
                org_id, body.adminEmail.strip(), role="org:admin", inviter_user_id=user["clerk_id"],
                redirect_url=f"{settings.app_base_url.rstrip('/')}/register",
            )
            email_sent = True
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Clerk org creation failed: {e}")
    return _to_org_out(org_id, body.name, email_sent=email_sent)


@router.get("/orgs", response_model=list[OrgOut])
def list_orgs(user: dict = Depends(require_superuser)):
    return [_to_org_out(o["clerk_org_id"], o["name"], o.get("created_at")) for o in auth_db.list_clerk_orgs()]


# ------------------------------------------------------------------ turk admins
# Platform-level reviewers/admins (not tied to an org). Superuser invites by email
# via a Clerk application invitation; the email match flags them turk_admin at sync.
class TurkAdminInviteInput(BaseModel):
    email: str


@router.post("/turk-admins/invite")
def invite_turk_admin(body: TurkAdminInviteInput, user: dict = Depends(require_superuser)):
    email = body.email.strip()
    auth_db.add_turk_admin_invite(email)
    try:
        clerk_api.create_application_invitation(
            email, redirect_url=f"{settings.app_base_url.rstrip('/')}/register"
        )
    except Exception as e:
        # Pending row is recorded regardless; surface the delivery error.
        raise HTTPException(status_code=502, detail=f"Clerk invite email failed: {e}")
    return {"ok": True, "emailSent": True}


@router.get("/turk-admins", response_model=list[UserOut])
def list_turk_admins(user: dict = Depends(require_superuser)):
    return [to_user_out(u) for u in auth_db.list_users_by_role("turk_admin")]


# ----------------------------------------------------------------------- staff
# Staff = org admins. Admins invite other staff BY EMAIL (always org:admin role);
# Clerk sends the email. Regular uploader users join only via referral links.
class StaffInviteInput(BaseModel):
    email: str


@router.post("/staff/invite")
def invite_staff(body: StaffInviteInput, actor: dict = Depends(_staff_roles)):
    org_id = actor.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="You must be in an organization to invite staff")
    try:
        clerk_api.create_organization_invitation(
            org_id, body.email.strip(), role="org:admin",
            inviter_user_id=actor["clerk_id"],
            redirect_url=f"{settings.app_base_url.rstrip('/')}/register",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Clerk staff invite failed: {e}")
    return {"ok": True, "emailSent": True}


@router.get("/staff")
def list_staff(actor: dict = Depends(_staff_roles)):
    """Members of the actor's Clerk org (email + role), via the Clerk Backend API."""
    org_id = actor.get("org_id")
    if not org_id:
        return []
    try:
        members = clerk_api.list_members(org_id)
    except Exception:
        members = []
    out = []
    for m in members:
        pud = m.get("public_user_data") or {}
        name = " ".join(filter(None, [pud.get("first_name"), pud.get("last_name")])).strip()
        out.append({
            "email": pud.get("identifier"),
            "name": name or pud.get("identifier"),
            "role": "admin" if (m.get("role") or "").endswith("admin") else "user",
        })
    return out


# ---------------------------------------------------------------------- users
@router.get("/users", response_model=list[UserOut])
def list_users(user: dict = Depends(require_superuser)):
    org_id = None if user["role"] == "superuser" else user["org_id"]
    return [to_user_out(u) for u in auth_db.list_users(org_id)]


# Note: user invites use each user's permanent referral code (/register?ref=<referralCode>),
# surfaced client-side — there is no token-minting endpoint.


@router.post("/users/{user_id}/role", response_model=UserOut)
# Org roles, membership, and invitations are managed in Clerk's <OrganizationProfile>
# (native UI + email invites). 'block' below is our own app-level lockout (enforced in
# deps.get_current_user) and is superuser-only.


def _block(user_id: int, blocked: bool, actor: dict) -> UserOut:
    target = auth_db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target["id"] == actor["id"] or target["role"] == "superuser":
        raise HTTPException(status_code=403, detail="Cannot block this account")
    return to_user_out(auth_db.set_user_blocked(user_id, blocked))


@router.post("/users/{user_id}/block", response_model=UserOut)
def block_user(user_id: int, actor: dict = Depends(require_superuser)):
    return _block(user_id, True, actor)


@router.post("/users/{user_id}/unblock", response_model=UserOut)
def unblock_user(user_id: int, actor: dict = Depends(require_superuser)):
    return _block(user_id, False, actor)


# ------------------------------------------------------------------- analytics
@router.get("/analytics", response_model=OrgAnalytics)
def analytics(user: dict = Depends(_analytics_roles)):
    """Superuser/turk_admin: platform-wide. Org admin: their org only."""
    if user["role"] in ("superuser", "turk_admin"):
        agg = submissions_db.analytics(None)
        total_users, blocked = auth_db.count_users(None)
        return OrgAnalytics(scope="platform", orgName=None, users=total_users,
                            blockedUsers=blocked, **agg)
    org = auth_db.get_clerk_org(user["org_id"]) if user["org_id"] else None
    agg = submissions_db.analytics(user["org_id"])
    total_users, blocked = auth_db.count_users(user["org_id"])
    return OrgAnalytics(scope="org", orgName=org["name"] if org else None, users=total_users,
                        blockedUsers=blocked, **agg)


@router.get("/analytics/users", response_model=list[UserStat])
def analytics_per_user(user: dict = Depends(_analytics_roles)):
    """Per-user submission breakdown. Superuser/turk_admin: all; org admin: their org."""
    org_id = None if user["role"] in ("superuser", "turk_admin") else user["org_id"]
    stats = submissions_db.per_user_stats(org_id)
    out = []
    for s in stats:
        try:
            u = auth_db.get_user_by_id(int(s["user_id"]))
        except (TypeError, ValueError):
            u = None
        out.append(UserStat(
            userId=int(s["user_id"]) if str(s["user_id"]).isdigit() else 0,
            username=u["username"] if u else f"user:{s['user_id']}",
            total=s["total"], accepted=s["accepted"], invalid=s["invalid"],
            inReview=s["in_review"], duplicate=s["duplicate"], points=s["points"],
        ))
    out.sort(key=lambda x: x.total, reverse=True)
    return out
