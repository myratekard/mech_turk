"""The /api contract the frontend (artifacts/turk) speaks, backed by our engine.

Mounted under the "/api" prefix in app/main.py. Auth is stubbed to a fixed dev
user (Clerk was stripped from the frontend for the self-contained build).
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

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

# Verdict helpers live in app/services/processing.py (shared by the sync path and the async
# worker). Re-exported here so existing imports (e.g. admin re-run) keep working.
from app.services.processing import (  # noqa: E402
    map_status_points, apply_african_gate, platform_label,
    regular_duplicate_points, self_duplicate_points,
)


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
    try:
        data = await request.body()
    except ClientDisconnect:
        # The client dropped mid-upload (slow/flaky connection or navigated away). Nothing to
        # save — return a clean 4xx instead of letting it surface as an unhandled 500 traceback.
        return JSONResponse(
            status_code=499,
            content={"error": "Upload interrupted — the connection dropped before the file finished uploading. Please try again."},
        )
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


def _analysis(row: dict) -> dict:
    aj = row.get("analysis_json")
    if not aj:
        return {}
    try:
        return json.loads(aj)
    except Exception:
        return {}


def _african_descent(row: dict):
    """The LLM's informational guess, stored as a top-level key in analysis_json."""
    return _analysis(row).get("appears_african_descent")


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
        africanClass=_analysis(row).get("african_classification"),
        acctHandle=row.get("acct_handle"),
        orgId=str(row["org_id"]) if row.get("org_id") else None,
        orgName=_org_name(row.get("org_id")),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


@router.post("/submissions", response_model=Submission, status_code=201, tags=["submissions"])
def create_submission(body: SubmissionInput, user: dict = Depends(get_current_user)):
    _t0 = time.perf_counter()
    def _lap(label: str) -> str:
        return f"{label}={(time.perf_counter() - _t0) * 1000:.0f}ms"
    _marks = []

    data = storage.read_object(body.objectPath)
    _marks.append(_lap("r2_read"))
    if data is None:
        raise HTTPException(status_code=400, detail="Uploaded object not found")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"Image is too large (max {settings.max_upload_mb} MB)."
        )

    # Exact-content fingerprint (sha256 of the raw bytes) — indexed, so a true re-upload is
    # caught with one O(1) lookup instead of the O(n) Hamming scan below.
    content_hash = hashlib.sha256(data).hexdigest()
    uid = str(user["id"])

    # 1) Rate limit: cap uploads per user / 24h.
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    if submissions_db.count_user_uploads_since(uid, since) >= settings.daily_upload_limit:
        raise HTTPException(status_code=429, detail="Daily upload limit reached. Try again later.")

    # ASYNC MODE: store as 'queued' and return instantly; the background worker runs the full
    # pipeline (gate + dedup + LLM/CV + African gate) and updates the verdict. Keeps ingest fast
    # and resilient. (Off => the legacy synchronous path below.)
    if settings.async_processing:
        row = submissions_db.insert_submission(
            user_id=uid, org_id=user.get("org_id"), image_url=body.imageUrl,
            object_path=body.objectPath, file_name=body.fileName,
            platform=body.platform, status="queued", points=0, analysis_json=None,
            content_hash=content_hash,
        )
        print(f"[ingest] submission #{row['id']} queued (async)", flush=True)
        return _row_to_submission(row)

    # 1b) Cheap shape gate: reject obvious non-phone-screenshots before spending an LLM call.
    reason = image_gate.check_phone_screenshot(data)
    _marks.append(_lap("gate"))
    if reason:
        row = submissions_db.insert_submission(
            user_id=uid, org_id=user.get("org_id"), image_url=body.imageUrl,
            object_path=body.objectPath, file_name=body.fileName,
            platform=None, status="unsupported", points=0, analysis_json=None,
            content_hash=content_hash,
        )
        print(f"[timing] submission #{row['id']} unsupported(gate) | {' '.join(_marks)}", flush=True)
        return _row_to_submission(row)

    # 2) Image-hash pre-check: ONLY a near-EXACT re-upload of the same screenshot
    #    short-circuits the LLM here (256-bit dHash, tight threshold). Look-alike
    #    screenshots of DIFFERENT accounts no longer match — they fall through to the
    #    engine below, where the account-level handle check is the authority on dupes.
    # 2a) Fast path: exact re-upload (identical bytes) → one indexed lookup, no scan.
    match = submissions_db.find_exact_hash_match(content_hash)
    if match:
        img_hash = match.get("image_hash")  # same image → same dHash; reuse, skip recompute
        _marks.append(_lap("exact_hash"))
    else:
        # 2b) Fall back to the fuzzy near-EXACT dHash scan for re-compressed/look-alike re-uploads.
        try:
            img_hash = dhash(data)
        except Exception:
            img_hash = None
        match = submissions_db.find_phash_match(img_hash, settings.dhash_distance) if img_hash else None
        _marks.append(_lap("dhash+match"))
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
            content_hash=content_hash,
        )
        print(f"[timing] submission #{row['id']} duplicate(reupload) | {' '.join(_marks)}", flush=True)
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
            analysis_json=None, image_hash=img_hash, content_hash=content_hash,
        )
        return _row_to_submission(row)

    _marks.append(_lap("pipeline"))
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
        content_hash=content_hash,
    )
    _marks.append(_lap("total"))  # cumulative from start — last mark is the end-to-end time
    print(f"[timing] submission #{row['id']} {status} | {' '.join(_marks)}", flush=True)
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
