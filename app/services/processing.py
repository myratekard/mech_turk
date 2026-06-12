# ABOUTME: The submission verdict pipeline, decoupled from the request path so it can run either
# synchronously (legacy) or in the background worker (async). Given a stored submission row, it
# reads the image, runs dedup + the LLM/CV engine + the African gate, and returns the fields to
# persist. Idempotent: safe to re-run on the same row (recomputes from the stored R2 object).
from __future__ import annotations

import hashlib
import mimetypes
from typing import Optional

from app.core.config import settings
from app.services import image_gate, storage, submissions_db
from app.services.imagehash import dhash
from app.services.pipeline import analyze as run_pipeline

_PLATFORM_LABEL = {"instagram": "Instagram", "x": "X", "tiktok": "TikTok", "unknown": "Unknown"}


def platform_label(result) -> str:
    return _PLATFORM_LABEL.get(result.platform, "Unknown")


def map_status_points(result) -> tuple[str, int]:
    """Engine verdict -> (submission status, points).
      not a profile shot -> unsupported · verified -> accepted(+points)
      low-confidence -> in_review · not verified -> invalid
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
    """African is a deciding factor on a would-be ACCEPT: african(>=min)->accepted,
    non_african(>=min)->invalid (ineligible/disputable), else->in_review."""
    if status != "accepted" or not settings.african_gate_enabled:
        return status, points
    cls = result.african_classification
    conf = result.african_confidence or 0.0
    if cls == "african" and conf >= settings.african_conf_min:
        return "accepted", points
    if cls == "non_african" and conf >= settings.african_conf_min:
        return "invalid", 0
    return "in_review", 0


def _duplicate_points(user_id) -> int:
    """Unified rule: the first `duplicate_grace_count` duplicates a user accumulates (regular OR
    self, combined) cost 0; every duplicate after that is `points_duplicate` (-2)."""
    if submissions_db.count_user_duplicates_total(str(user_id)) < settings.duplicate_grace_count:
        return 0
    return settings.points_duplicate


# Both duplicate kinds now share the same penalty curve; the dup_kind label is still recorded
# (for display / counts) but no longer changes the points.
def regular_duplicate_points(user_id) -> int:
    return _duplicate_points(user_id)


def self_duplicate_points(user_id) -> int:
    return _duplicate_points(user_id)


def process_submission(row: dict) -> dict:
    """Compute the verdict for a stored submission row. Returns the fields to persist
    (status, points, platform, analysis_json, acct_*, image_hash, content_hash, dup_kind).
    Excludes the row's own id from dedup matches, so it's safe to run after the row exists.
    """
    sid = row["id"]
    uid = str(row["user_id"])
    data = storage.read_object(row["object_path"])
    if data is None:
        return {"status": "invalid", "points": 0, "analysis_json": None}

    content_hash = row.get("content_hash") or hashlib.sha256(data).hexdigest()

    # Cheap shape gate.
    if image_gate.check_phone_screenshot(data):
        return {"status": "unsupported", "points": 0, "analysis_json": None, "content_hash": content_hash}

    # Dedup: exact-bytes (O(1)) then near-exact dHash, excluding this row.
    match = submissions_db.find_exact_hash_match(content_hash, exclude_id=sid)
    if match:
        img_hash = match.get("image_hash")
    else:
        try:
            img_hash = dhash(data)
        except Exception:
            img_hash = None
        match = submissions_db.find_phash_match(img_hash, settings.dhash_distance, exclude_id=sid) if img_hash else None
    if match:
        same_user = match["user_id"] == uid
        dup_kind, points = ("self", self_duplicate_points(uid)) if same_user else ("regular", regular_duplicate_points(uid))
        return {
            "status": "duplicate", "points": points, "platform": match.get("platform"),
            "analysis_json": match.get("analysis_json"), "acct_platform": match.get("acct_platform"),
            "acct_handle": match.get("acct_handle"), "image_hash": img_hash, "content_hash": content_hash,
            "dup_kind": dup_kind, "update_acct": True,
        }

    # Novel image -> engine.
    mime, _ = mimetypes.guess_type(row.get("file_name") or row["object_path"])
    try:
        result = run_pipeline(data, mime=mime or "image/jpeg", persist=False, force_profile=True)
    except Exception:
        return {"status": "in_review", "points": 0, "analysis_json": None, "image_hash": img_hash, "content_hash": content_hash}

    status, points = map_status_points(result)
    status, points = apply_african_gate(result, status, points)
    platform = row.get("platform") or platform_label(result)
    acct_platform = result.platform if result.platform != "unknown" else None
    acct_handle = submissions_db.normalize_handle(getattr(result.profile, "handle", None))
    dup_kind = None
    if status == "accepted" and submissions_db.is_duplicate_capture(acct_platform, acct_handle, exclude_id=sid):
        status, points, dup_kind = "duplicate", regular_duplicate_points(uid), "regular"
    return {
        "status": status, "points": points, "platform": platform,
        "analysis_json": result.model_dump_json(), "acct_platform": acct_platform,
        "acct_handle": acct_handle, "image_hash": img_hash, "content_hash": content_hash,
        "dup_kind": dup_kind, "update_acct": True,
    }
