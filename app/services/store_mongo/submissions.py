"""MongoDB implementation of the submissions store.

Mirrors store_sqlite/submissions.py exactly — same function signatures, same dict shapes
(integer `id` preserved via the counters collection), same status/points/dispute semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING

from app.core.config import settings
from app.services.mongo_client import clean, col, db, next_id

_COL = "submissions"

# Final states an uploader may contest into the review queue (duplicates excluded).
DISPUTABLE_STATUSES = ("accepted", "invalid")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _c():
    return col(_COL)


def init_db() -> None:
    c = _c()
    c.create_index([("user_id", ASCENDING)])
    c.create_index([("status", ASCENDING)])
    c.create_index([("image_hash", ASCENDING)])
    c.create_index([("acct_platform", ASCENDING), ("acct_handle", ASCENDING)])
    c.create_index([("org_id", ASCENDING)])
    c.create_index([("id", ASCENDING)], unique=True)


def insert_submission(
    *,
    user_id: str,
    image_url: str,
    object_path: str,
    file_name: Optional[str],
    platform: Optional[str],
    status: str,
    points: int,
    analysis_json: Optional[str],
    org_id: Optional[int] = None,
    acct_platform: Optional[str] = None,
    acct_handle: Optional[str] = None,
    image_hash: Optional[str] = None,
) -> dict:
    ts = _now()
    doc = {
        "id": next_id(_COL),
        "user_id": user_id,
        "org_id": org_id,
        "image_url": image_url,
        "object_path": object_path,
        "file_name": file_name,
        "platform": platform,
        "status": status,
        "points": points,
        "analysis_json": analysis_json,
        "acct_platform": acct_platform,
        "acct_handle": acct_handle,
        "image_hash": image_hash,
        "disputed": 0,
        "invoice_id": None,
        "settled": 0,
        "settled_at": None,
        "created_at": ts,
        "updated_at": ts,
    }
    _c().insert_one(doc)
    return clean(doc)


# --------------------------------------------------------------- review queue
def count_review_queue() -> int:
    return int(_c().count_documents({"status": "in_review"}))


def list_review_queue(page: int, limit: int) -> Tuple[List[dict], int]:
    c = _c()
    total = c.count_documents({"status": "in_review"})
    rows = c.find({"status": "in_review"}, {"_id": 0}).sort("id", DESCENDING).skip((page - 1) * limit).limit(limit)
    return list(rows), int(total)


def normalize_handle(handle: Optional[str]) -> Optional[str]:
    if not handle:
        return None
    h = handle.strip().lstrip("@").lower()
    return h or None


def is_duplicate_capture(
    acct_platform: Optional[str], acct_handle: Optional[str], exclude_id: Optional[int] = None
) -> bool:
    if not acct_platform or not acct_handle:
        return False
    q: dict = {"status": "accepted", "acct_platform": acct_platform, "acct_handle": acct_handle}
    if exclude_id is not None:
        q["id"] = {"$ne": exclude_id}
    return _c().count_documents(q) > 0


def analytics(org_id: Optional[int] = None) -> dict:
    q = {} if org_id is None else {"org_id": org_id}
    rows = list(_c().find(q, {"_id": 0, "status": 1, "points": 1}))
    return {
        "totalSubmissions": len(rows),
        "accepted": sum(1 for r in rows if r["status"] == "accepted"),
        "invalid": sum(1 for r in rows if r["status"] == "invalid"),
        "inReview": sum(1 for r in rows if r["status"] == "in_review"),
        "duplicate": sum(1 for r in rows if r["status"] == "duplicate"),
        "unsupported": sum(1 for r in rows if r["status"] == "unsupported"),
        "totalPoints": sum(r.get("points", 0) for r in rows),
    }


def per_user_stats(org_id: Optional[int] = None) -> List[dict]:
    match = {} if org_id is None else {"org_id": org_id}

    def _sum_if(status):
        return {"$sum": {"$cond": [{"$eq": ["$status", status]}, 1, 0]}}

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": "$user_id",
            "total": {"$sum": 1},
            "accepted": _sum_if("accepted"),
            "invalid": _sum_if("invalid"),
            "in_review": _sum_if("in_review"),
            "duplicate": _sum_if("duplicate"),
            "unsupported": _sum_if("unsupported"),
            "points": {"$sum": "$points"},
        }},
    ]
    out = []
    for r in _c().aggregate(pipeline):
        out.append({
            "user_id": r["_id"], "total": r["total"], "accepted": r["accepted"] or 0,
            "invalid": r["invalid"] or 0, "in_review": r["in_review"] or 0,
            "duplicate": r["duplicate"] or 0, "unsupported": r["unsupported"] or 0,
            "points": r["points"] or 0,
        })
    return out


def count_user_regular_duplicates(user_id: str) -> int:
    """A user's REGULAR duplicates (not self-duplicates) — drives the eased penalty."""
    return int(_c().count_documents(
        {"user_id": user_id, "status": "duplicate", "points": {"$ne": settings.points_self_duplicate}}
    ))


def count_user_uploads_since(user_id: str, since_iso: str) -> int:
    return int(_c().count_documents({"user_id": user_id, "created_at": {"$gte": since_iso}}))


def find_phash_match(image_hash: str, max_distance: int, limit: int = 5000) -> Optional[dict]:
    if not image_hash:
        return None
    from app.services.imagehash import hamming
    rows = _c().find({"image_hash": {"$ne": None}}, {"_id": 0}).sort("id", DESCENDING).limit(limit)
    best, best_d = None, max_distance + 1
    for r in rows:
        d = hamming(image_hash, r["image_hash"])
        if d <= max_distance and d < best_d:
            best, best_d = r, d
            if d == 0:
                break
    return best


def reassign_user(old_user_id: str, new_user_id: str) -> int:
    res = _c().update_many({"user_id": old_user_id}, {"$set": {"user_id": new_user_id}})
    return int(res.modified_count)


def get_submission_any(submission_id: int) -> Optional[dict]:
    return _c().find_one({"id": submission_id}, {"_id": 0})


def update_submission_status(
    submission_id: int, status: str, points: int, analysis_json: Optional[str] = None,
    acct_platform: Optional[str] = None, acct_handle: Optional[str] = None,
    update_acct: bool = False,
) -> Optional[dict]:
    sets: dict = {"status": status, "points": points, "updated_at": _now()}
    if analysis_json is not None:
        sets["analysis_json"] = analysis_json
    if update_acct:
        sets["acct_platform"] = acct_platform
        sets["acct_handle"] = acct_handle
    _c().update_one({"id": submission_id}, {"$set": sets})
    return _c().find_one({"id": submission_id}, {"_id": 0})


def dispute_submission(user_id: str, submission_id: int) -> Tuple[Optional[dict], Optional[str]]:
    row = _c().find_one({"id": submission_id, "user_id": user_id})
    if row is None:
        return None, "not_found"
    if int(row.get("disputed") or 0) == 1:
        return None, "already_disputed"
    if row["status"] not in DISPUTABLE_STATUSES:
        return None, "not_disputable"
    _c().update_one(
        {"id": submission_id},
        {"$set": {"status": "in_review", "disputed": 1, "updated_at": _now()}},
    )
    return _c().find_one({"id": submission_id}, {"_id": 0}), None


def list_submissions(
    user_id: str, status: Optional[str], page: int, limit: int
) -> Tuple[List[dict], int]:
    q: dict = {"user_id": user_id}
    if status:
        q["status"] = status
    c = _c()
    total = c.count_documents(q)
    rows = c.find(q, {"_id": 0}).sort("id", DESCENDING).skip((page - 1) * limit).limit(limit)
    return list(rows), int(total)


def get_submission(user_id: str, submission_id: int) -> Optional[dict]:
    return _c().find_one({"id": submission_id, "user_id": user_id}, {"_id": 0})


def recent_submissions(user_id: str, n: int = 5) -> List[dict]:
    return list(_c().find({"user_id": user_id}, {"_id": 0}).sort("id", DESCENDING).limit(n))


def dashboard_summary(user_id: str) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    rows = list(_c().find({"user_id": user_id}, {"_id": 0, "status": 1, "points": 1, "updated_at": 1}))
    total_points = sum(r.get("points", 0) for r in rows)
    accepted = sum(1 for r in rows if r["status"] == "accepted")
    in_review = sum(1 for r in rows if r["status"] == "in_review")
    processed = sum(1 for r in rows if r["status"] == "processed")
    invalid = sum(1 for r in rows if r["status"] == "invalid")
    duplicate = sum(1 for r in rows if r["status"] == "duplicate")
    unsupported = sum(1 for r in rows if r["status"] == "unsupported")
    updated_today = sum(1 for r in rows if (r.get("updated_at") or "").startswith(today))

    accepted_pts = sum(r.get("points", 0) for r in rows if r["status"] == "accepted")
    duplicate_pts = sum(r.get("points", 0) for r in rows if r["status"] == "duplicate")
    points_breakdown = [
        {"key": "accepted", "label": "Accepted captures", "count": accepted, "points": accepted_pts},
        {"key": "duplicate", "label": "Duplicate penalties", "count": duplicate, "points": duplicate_pts},
        {"key": "in_review", "label": "Pending review", "count": in_review, "points": 0},
        {"key": "invalid", "label": "Rejected / invalid", "count": invalid, "points": 0},
        {"key": "unsupported", "label": "Unsupported", "count": unsupported, "points": 0},
    ]

    return {
        "totalPoints": total_points,
        "totalSubmissions": len(rows),
        "accepted": accepted,
        "inReview": in_review,
        "processed": processed,
        "invalid": invalid,
        "duplicate": duplicate,
        "unsupported": unsupported,
        "updatedToday": updated_today,
        "pointsBreakdown": points_breakdown,
    }


# ------------------------------------------------------------------- invoices
INVOICEABLE_STATUSES = ("accepted", "duplicate")


def _inv():
    return col("invoices")


def outstanding_summary(org_id: str) -> dict:
    q = {"org_id": org_id, "invoice_id": None, "status": {"$in": list(INVOICEABLE_STATUSES)}}
    rows = list(_c().find(q, {"_id": 0, "points": 1}))
    return {"count": len(rows), "points": sum(r.get("points", 0) for r in rows)}


def create_invoice(org_id: str, created_by) -> Optional[dict]:
    ts = _now()
    q = {"org_id": org_id, "invoice_id": None, "status": {"$in": list(INVOICEABLE_STATUSES)}}
    rows = list(_c().find(q, {"_id": 0, "id": 1, "points": 1}))
    if not rows:
        return None
    ids = [r["id"] for r in rows]
    total = sum(r.get("points", 0) for r in rows)
    inv = {
        "id": next_id("invoices"), "org_id": org_id, "status": "pending",
        "total_points": total, "submission_count": len(ids), "created_by": str(created_by),
        "created_at": ts, "settled_by": None, "settled_at": None,
    }
    _inv().insert_one(inv)
    _c().update_many({"id": {"$in": ids}}, {"$set": {"invoice_id": inv["id"]}})
    return clean(inv)


def list_invoices(org_id: Optional[str] = None) -> List[dict]:
    q = {} if org_id is None else {"org_id": org_id}
    return list(_inv().find(q, {"_id": 0}).sort("id", DESCENDING))


def get_invoice(invoice_id: int) -> Optional[dict]:
    inv = _inv().find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        return None
    items = list(_c().find(
        {"invoice_id": invoice_id},
        {"_id": 0, "id": 1, "user_id": 1, "platform": 1, "acct_handle": 1, "status": 1, "points": 1, "created_at": 1},
    ).sort("id", 1))
    inv["items"] = items
    return inv


def settle_invoice(invoice_id: int, settled_by) -> Tuple[Optional[dict], Optional[str]]:
    ts = _now()
    inv = _inv().find_one({"id": invoice_id})
    if not inv:
        return None, "not_found"
    if inv.get("status") == "settled":
        return None, "already_settled"
    _inv().update_one({"id": invoice_id}, {"$set": {"status": "settled", "settled_by": str(settled_by), "settled_at": ts}})
    _c().update_many({"invoice_id": invoice_id}, {"$set": {"settled": 1, "settled_at": ts}})
    return _inv().find_one({"id": invoice_id}, {"_id": 0}), None
