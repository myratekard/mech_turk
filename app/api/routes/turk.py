"""The /api contract the frontend (artifacts/turk) speaks, backed by our engine.

Mounted under the "/api" prefix in app/main.py. Auth is stubbed to a fixed dev
user (Clerk was stripped from the frontend for the self-contained build).
"""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

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
from app.services.imagehash import average_hash
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


def platform_label(result) -> str:
    return _PLATFORM_LABEL.get(result.platform, "Unknown")


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
    storage.save_bytes(object_id, data)
    return {"ok": True, "objectPath": storage.object_path_for(object_id)}


@router.get("/storage/objects/{object_path:path}", tags=["Storage"])
def get_storage_object(object_path: str):
    f = storage.object_file(object_path.split("/")[-1])
    if not f:
        return JSONResponse(status_code=404, content={"error": "Object not found"})
    media_type, _ = mimetypes.guess_type(str(f))
    return FileResponse(str(f), media_type=media_type or "application/octet-stream")


@router.get("/storage/public-objects/{file_path:path}", tags=["Storage"])
def get_public_object(file_path: str):
    # Public assets (logo, etc.) are served by Vite from /public in this build.
    return JSONResponse(status_code=404, content={"error": "File not found"})


# ---------------------------------------------------------------------- submissions
def _row_to_submission(row: dict) -> Submission:
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
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


@router.post("/submissions", response_model=Submission, status_code=201, tags=["submissions"])
def create_submission(body: SubmissionInput, user: dict = Depends(get_current_user)):
    data = storage.read_object(body.objectPath)
    if data is None:
        raise HTTPException(status_code=400, detail="Uploaded object not found")

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

    # 2) Perceptual-hash pre-check: a re-uploaded / near-identical image skips the LLM
    #    entirely (no token spend). Re-uploading your own image is penalized.
    try:
        img_hash = average_hash(data)
    except Exception:
        img_hash = None
    match = submissions_db.find_phash_match(img_hash, settings.phash_distance) if img_hash else None
    if match:
        # Self-duplicate = the same user re-uploading the same image; others' re-upload = duplicate.
        same_user = match["user_id"] == uid
        points = settings.points_self_duplicate if same_user else settings.points_duplicate
        row = submissions_db.insert_submission(
            user_id=uid, org_id=user.get("org_id"), image_url=body.imageUrl,
            object_path=body.objectPath, file_name=body.fileName,
            platform=match["platform"], status="duplicate", points=points,
            analysis_json=match["analysis_json"], acct_platform=match["acct_platform"],
            acct_handle=match["acct_handle"], image_hash=img_hash,
        )
        return _row_to_submission(row)

    # 3) Novel image -> run the engine (the only path that spends tokens).
    #    force_profile=True keeps the fields the LLM already extracted in this same call even
    #    when the verdict isn't "verified" — so a later invalid->accepted dispute needs NO re-run.
    mime, _ = mimetypes.guess_type(body.fileName or body.objectPath)
    try:
        result = run_pipeline(data, mime=mime or "image/jpeg", persist=False, force_profile=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")

    status, points = map_status_points(result)
    platform = body.platform or platform_label(result)

    # Account-level duplicate (same platform+handle already captured) earns no points.
    # acct_platform/acct_handle are stored for every verdict (not just accepted) so the handle
    # is available if the submission is later disputed and approved.
    acct_platform = result.platform if result.platform != "unknown" else None
    acct_handle = submissions_db.normalize_handle(getattr(result.profile, "handle", None))
    if status == "accepted" and submissions_db.is_duplicate_capture(acct_platform, acct_handle):
        status, points = "duplicate", settings.points_duplicate

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
