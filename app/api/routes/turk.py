"""The /api contract the frontend (artifacts/turk) speaks, backed by our engine.

Mounted under the "/api" prefix in app/main.py. Auth is stubbed to a fixed dev
user (Clerk was stripped from the frontend for the self-contained build).
"""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import settings
from app.schemas.api_models import (
    DashboardSummary,
    HealthStatus,
    Submission,
    SubmissionInput,
    SubmissionList,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services import image_gate, storage, submissions_db
from app.services.imagehash import dhash
from app.services.pipeline import analyze as run_pipeline

router = APIRouter()

_PLATFORM_LABEL = {"instagram": "Instagram", "x": "X", "tiktok": "TikTok", "unknown": "Unknown"}


def map_status_points(result) -> tuple[str, int]:
    """Engine verdict -> (submission status, points). Shared with admin re-run.

      not a profile shot -> unsupported (out of scope; not a profile page)
      verified           -> accepted (+points)
      low-confidence      -> in_review (needs a human look)
      not a verified acct -> invalid (rejected; we only want verified accounts)
    """
    if not getattr(result, "is_profile_screenshot", True):
        return "unsupported", 0
    v = result.verification
    if v.needs_review:
        return "in_review", 0
    if v.verified:
        return "accepted", settings.points_accepted
    return "invalid", 0


def apply_african_gate(result, status: str, points: int) -> tuple[str, int]:
    """African is a deciding factor: only gate a would-be ACCEPT (verified) submission.

      african     (conf >= min) -> stays accepted (eligible)
      non_african (conf >= min) -> invalid (ineligible — disputable)
      generic / unclear / low-confidence -> in_review (human decides; low-conf routes here)
    Other statuses (unsupported / invalid / already in_review) are left untouched.
    """
    if status != "accepted" or not settings.african_gate_enabled:
        return status, points
    cls = result.african_classification
    conf = result.african_confidence or 0.0
    if cls == "african" and conf >= settings.african_conf_min:
        return "accepted", points
    if cls == "non_african" and conf >= settings.african_conf_min:
        return "invalid", 0
    return "in_review", 0


def platform_label(result) -> str:
    return _PLATFORM_LABEL.get(result.platform, "Unknown")


def regular_duplicate_points(user_id) -> int:
    """Regular-duplicate penalty: points_duplicate (-2) by default, escalating to
    points_duplicate_escalated (-5) once the user passes duplicate_escalate_threshold
    regular duplicates."""
    if submissions_db.count_user_regular_duplicates(str(user_id)) >= settings.duplicate_escalate_threshold:
        return settings.points_duplicate_escalated
    return settings.points_duplicate


def self_duplicate_points(user_id) -> int:
    """Escalating self-duplicate penalty: first N = warning (0), next M = mid penalty, then -10."""
    n = submissions_db.count_user_self_duplicates(str(user_id))
    if n < settings.self_dup_warn_count:
        return 0
    if n < settings.self_dup_warn_count + settings.self_dup_mid_count:
        return settings.self_dup_mid_penalty
    return settings.points_self_duplicate


# --------------------------------------------------------------------------- health
@router.get("/healthz", response_model=HealthStatus, tags=["health"])
def health_check():
    return HealthStatus(status="ok")


# -------------------------------------------------------------------------- storage
@router.post("/storage/uploads/request-url", response_model=UploadUrlResponse, tags=["Storage"])
def request_upload_url(body: UploadUrlRequest):
    object_id = storage.new_object_id(body.name)
    return UploadUrlResponse(
        uploadURL=storage.upload_url_for(object_id),
        objectPath=storage.object_path_for(object_id),
        metadata=body,
    )


@router.put("/storage/upload/{object_id}", tags=["Storage"])
async def upload_object(object_id: str, request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload body")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image is too large (max {settings.max_upload_mb} MB).",
        )
    storage.save_bytes(object_id, data)
    return {"ok": True, "objectPath": storage.object_path_for(object_id)}


@router.get("/storage/objects/{object_path:path}", tags=["Storage"])
def get_storage_object(object_path: str):
    object_id = object_path.split("/")[-1]
    data = storage.read_object(object_id)  # works for local disk and R2
    if data is None:
        return JSONResponse(status_code=404, content={"error": "Object not found"})
    media_type, _ = mimetypes.guess_type(object_id)
    return Response(content=data, media_type=media_type or "application/octet-stream")


@router.get("/storage/public-objects/{file_path:path}", tags=["Storage"])
def get_public_object(file_path: str):
    # Public assets (logo, etc.) are served by Vite from /public in this build.
    return JSONResponse(status_code=404, content={"error": "File not found"})


# ---------------------------------------------------------------------- submissions
_ORG_NAME_CACHE: dict = {}


def _org_name(org_id) -> Optional[str]:
    """Cached Clerk-org display name (for the 'settled via {org}' note)."""
    if not org_id:
        return None
    if org_id not in _ORG_NAME_CACHE:
        from app.services import auth_db
        org = auth_db.get_clerk_org(str(org_id))
        _ORG_NAME_CACHE[org_id] = (org or {}).get("name")
    return _ORG_NAME_CACHE[org_id]


def _african_descent(row: dict):
    """The LLM's informational guess, stored as a top-level key in analysis_json."""
    aj = row.get("analysis_json")
    if not aj:
        return None
    try:
        return json.loads(aj).get("appears_african_descent")
    except Exception:
        return None


def _row_to_submission(row: dict) -> Submission:
    settled = bool(row.get("settled") or 0)
    return Submission(
        id=row["id"],
        userId=row["user_id"],
        imageUrl=row["image_url"],
        objectPath=row["object_path"],
        fileName=row["file_name"],
        platform=row["platform"],
        status=row["status"],
        points=row["points"],
        disputed=bool(row.get("disputed") or 0),
        dupKind=row.get("dup_kind"),
        settled=settled,
        settledAt=row.get("settled_at"),
        settledVia=_org_name(row.get("org_id")) if settled else None,
        africanDescent=_african_descent(row),
        acctHandle=row.get("acct_handle"),
        orgId=str(row["org_id"]) if row.get("org_id") else None,
        orgName=_org_name(row.get("org_id")),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


@router.post("/submissions", response_model=Submission, status_code=201, tags=["submissions"])
def create_submission(body: SubmissionInput, user: dict = Depends(get_current_user)):
    data = storage.read_object(body.objectPath)
    if data is None:
        raise HTTPException(status_code=400, detail="Uploaded object not found")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"Image is too large (max {settings.max_upload_mb} MB)."
        )

    uid = str(user["id"])

    # 1) Rate limit: cap uploads per user / 24h.
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    if submissions_db.count_user_uploads_since(uid, since) >= settings.daily_upload_limit:
        raise HTTPException(status_code=429, detail="Daily upload limit reached. Try again later.")

    # 1b) Cheap shape gate: reject obvious non-phone-screenshots before spending an LLM call.
    reason = image_gate.check_phone_screenshot(data)
    if reason:
        row = submissions_db.insert_submission(
            user_id=uid, org_id=user.get("org_id"), image_url=body.imageUrl,
            object_path=body.objectPath, file_name=body.fileName,
            platform=None, status="unsupported", points=0, analysis_json=None,
        )
        return _row_to_submission(row)

    # 2) Image-hash pre-check: ONLY a near-EXACT re-upload of the same screenshot
    #    short-circuits the LLM here (256-bit dHash, tight threshold). Look-alike
    #    screenshots of DIFFERENT accounts no longer match — they fall through to the
    #    engine below, where the account-level handle check is the authority on dupes.
    try:
        img_hash = dhash(data)
    except Exception:
        img_hash = None
    match = submissions_db.find_phash_match(img_hash, settings.dhash_distance) if img_hash else None
    if match:
        # Self-duplicate = the same user re-uploading the same image; others' re-upload = duplicate.
        same_user = match["user_id"] == uid
        if same_user:
            dup_kind, points = "self", self_duplicate_points(uid)
        else:
            dup_kind, points = "regular", regular_duplicate_points(uid)
        row = submissions_db.insert_submission(
            user_id=uid, org_id=user.get("org_id"), image_url=body.imageUrl,
            object_path=body.objectPath, file_name=body.fileName,
            platform=match["platform"], status="duplicate", points=points,
            analysis_json=match["analysis_json"], acct_platform=match["acct_platform"],
            acct_handle=match["acct_handle"], image_hash=img_hash, dup_kind=dup_kind,
        )
        return _row_to_submission(row)

    # 3) Novel image -> run the engine (the only path that spends tokens).
    #    force_profile=True keeps the fields the LLM already extracted in this same call even
    #    when the verdict isn't "verified" — so a later invalid->accepted dispute needs NO re-run.
    mime, _ = mimetypes.guess_type(body.fileName or body.objectPath)
    try:
        result = run_pipeline(data, mime=mime or "image/jpeg", persist=False, force_profile=True)
    except Exception:
        # LLM unavailable (after retries) — don't lose the upload or reject the user. Record
        # it and route to the human review queue instead.
        row = submissions_db.insert_submission(
            user_id=uid, org_id=user.get("org_id"), image_url=body.imageUrl,
            object_path=body.objectPath, file_name=body.fileName,
            platform=body.platform, status="in_review", points=0,
            analysis_json=None, image_hash=img_hash,
        )
        return _row_to_submission(row)

    status, points = map_status_points(result)
    status, points = apply_african_gate(result, status, points)  # African eligibility gate
    platform = body.platform or platform_label(result)

    # Account-level duplicate (same platform+handle already captured) earns no points.
    # acct_platform/acct_handle are stored for every verdict (not just accepted) so the handle
    # is available if the submission is later disputed and approved.
    acct_platform = result.platform if result.platform != "unknown" else None
    acct_handle = submissions_db.normalize_handle(getattr(result.profile, "handle", None))
    dup_kind = None
    if status == "accepted" and submissions_db.is_duplicate_capture(acct_platform, acct_handle):
        status, points, dup_kind = "duplicate", regular_duplicate_points(uid), "regular"

    row = submissions_db.insert_submission(
        user_id=uid,
        org_id=user.get("org_id"),
        image_url=body.imageUrl,
        object_path=body.objectPath,
        file_name=body.fileName,
        platform=platform,
        status=status,
        points=points,
        analysis_json=result.model_dump_json(),
        acct_platform=acct_platform,
        acct_handle=acct_handle,
        image_hash=img_hash,
        dup_kind=dup_kind,
    )
    return _row_to_submission(row)


@router.get("/submissions", response_model=SubmissionList, tags=["submissions"])
def list_submissions(
    status: Optional[str] = Query(default=None, pattern="^(in_review|processed|accepted|invalid)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    rows, total = submissions_db.list_submissions(str(user["id"]), status, page, limit)
    return SubmissionList(
        submissions=[_row_to_submission(r) for r in rows],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/submissions/{submission_id}/dispute", response_model=Submission, tags=["submissions"])
def dispute_submission(submission_id: int, user: dict = Depends(get_current_user)):
    """Owner contests a decided submission (accepted or invalid): send it back to the
    review queue. Allowed once per submission; duplicates cannot be disputed."""
    row, err = submissions_db.dispute_submission(str(user["id"]), submission_id)
    if err == "not_found":
        raise HTTPException(status_code=404, detail="Submission not found")
    if err == "already_disputed":
        raise HTTPException(status_code=409, detail="This submission has already been disputed once.")
    if err == "not_disputable":
        raise HTTPException(
            status_code=400,
            detail="Only accepted or invalid submissions can be disputed.",
        )
    return _row_to_submission(row)


@router.get("/submissions/{submission_id}", response_model=Submission, tags=["submissions"])
def get_submission(submission_id: int, user: dict = Depends(get_current_user)):
    row = submissions_db.get_submission(str(user["id"]), submission_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return _row_to_submission(row)


# ------------------------------------------------------------------------ dashboard
@router.get("/dashboard/summary", response_model=DashboardSummary, tags=["dashboard"])
def dashboard_summary(user: dict = Depends(get_current_user)):
    return DashboardSummary(**submissions_db.dashboard_summary(str(user["id"])))


@router.get("/dashboard/recent", response_model=list[Submission], tags=["dashboard"])
def dashboard_recent(user: dict = Depends(get_current_user)):
    return [_row_to_submission(r) for r in submissions_db.recent_submissions(str(user["id"]), 5)]
