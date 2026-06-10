"""SQLite-backed store for submissions (and their full analysis JSON).

Self-contained: one file under the artifact dir. Safe for FastAPI's threaded
workers via a short-lived connection per call + WAL mode.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.config import settings

_DB_PATH = Path(settings.artifact_dir) / "turk.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                org_id      INTEGER,
                image_url   TEXT NOT NULL,
                object_path TEXT NOT NULL,
                file_name   TEXT,
                platform    TEXT,
                status      TEXT NOT NULL,
                points      INTEGER NOT NULL DEFAULT 0,
                analysis_json TEXT,
                acct_platform TEXT,
                acct_handle   TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
            """
        )
        # Migrations: add columns to pre-existing tables.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(submissions)").fetchall()}
        if "org_id" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN org_id INTEGER")
        if "acct_platform" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN acct_platform TEXT")
        if "acct_handle" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN acct_handle TEXT")
        if "image_hash" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN image_hash TEXT")
        if "disputed" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN disputed INTEGER NOT NULL DEFAULT 0")
        if "invoice_id" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN invoice_id INTEGER")
        if "settled" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN settled INTEGER NOT NULL DEFAULT 0")
        if "settled_at" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN settled_at TEXT")
        if "dup_kind" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN dup_kind TEXT")  # 'self' | 'regular' | null
        if "content_hash" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN content_hash TEXT")  # sha256 of raw bytes
        # Async-queue bookkeeping (background worker): claim/attempt/recovery.
        if "started_at" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN started_at TEXT")
        if "worker_id" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN worker_id TEXT")
        if "attempts" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        # Indexed exact-content lookup → O(1) detection of true re-uploads (no Hamming scan).
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sub_content_hash ON submissions(content_hash)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id      TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                total_points INTEGER NOT NULL DEFAULT 0,
                submission_count INTEGER NOT NULL DEFAULT 0,
                created_by  TEXT,
                created_at  TEXT NOT NULL,
                settled_by  TEXT,
                settled_at  TEXT
            )
            """
        )
        # Migration: invoice payment-receipt columns (proof attached at settle time).
        inv_cols = {r["name"] for r in conn.execute("PRAGMA table_info(invoices)").fetchall()}
        if "receipt_object_path" not in inv_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN receipt_object_path TEXT")
        if "receipt_amount" not in inv_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN receipt_amount REAL")


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
    dup_kind: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> dict:
    ts = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO submissions
                (user_id, org_id, image_url, object_path, file_name, platform, status, points,
                 analysis_json, acct_platform, acct_handle, image_hash, dup_kind, content_hash,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, org_id, image_url, object_path, file_name, platform, status, points,
             analysis_json, acct_platform, acct_handle, image_hash, dup_kind, content_hash, ts, ts),
        )
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


# --------------------------------------------------------------- review queue
def count_review_queue() -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) c FROM submissions WHERE status='in_review'").fetchone()["c"])


def list_review_queue(page: int, limit: int) -> Tuple[List[dict], int]:
    """Global pool of in_review submissions across all users/orgs."""
    offset = (page - 1) * limit
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM submissions WHERE status='in_review'"
        ).fetchone()["c"]
        rows = conn.execute(
            "SELECT * FROM submissions WHERE status='in_review' ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows], int(total)


def normalize_handle(handle: Optional[str]) -> Optional[str]:
    if not handle:
        return None
    h = handle.strip().lstrip("@").lower()
    return h or None


def is_duplicate_capture(
    acct_platform: Optional[str], acct_handle: Optional[str], exclude_id: Optional[int] = None
) -> bool:
    """True if the same (platform, handle) has already been CLAIMED by any user — i.e. a prior
    submission that is accepted, awaiting review, or already flagged duplicate. (invalid /
    unsupported don't count, since those never captured the account.) This is what stops a
    second person earning points for an account someone else already submitted."""
    if not acct_platform or not acct_handle:
        return False
    q = ("SELECT COUNT(*) c FROM submissions "
         "WHERE status IN ('accepted','in_review','duplicate') AND acct_platform=? AND acct_handle=?")
    params: list = [acct_platform, acct_handle]
    if exclude_id is not None:
        q += " AND id != ?"
        params.append(exclude_id)
    with _connect() as conn:
        return conn.execute(q, params).fetchone()["c"] > 0


def analytics(org_id: Optional[int] = None) -> dict:
    """Cumulative submission stats for an org (org_id set) or platform-wide (None)."""
    where, params = "", ()
    if org_id is not None:
        where, params = "WHERE org_id=?", (org_id,)
    with _connect() as conn:
        rows = conn.execute(f"SELECT status, points, settled FROM submissions {where}", params).fetchall()
    total_points = sum(r["points"] for r in rows)
    settled_points = sum(r["points"] for r in rows if r["settled"])
    return {
        "totalSubmissions": len(rows),
        "accepted": sum(1 for r in rows if r["status"] == "accepted"),
        "invalid": sum(1 for r in rows if r["status"] == "invalid"),
        "inReview": sum(1 for r in rows if r["status"] == "in_review"),
        "duplicate": sum(1 for r in rows if r["status"] == "duplicate"),
        "unsupported": sum(1 for r in rows if r["status"] == "unsupported"),
        "processing": sum(1 for r in rows if r["status"] in ("queued", "processing")),
        "totalPoints": total_points,
        "settledPoints": settled_points,
        "unsettledPoints": total_points - settled_points,
    }


def per_user_stats(org_id: Optional[int] = None) -> List[dict]:
    """Per-user submission breakdown for the analytics dashboards."""
    where, params = "", ()
    if org_id is not None:
        where, params = "WHERE org_id=?", (org_id,)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT user_id,
                   COUNT(*) AS total,
                   SUM(status='accepted')  AS accepted,
                   SUM(status='invalid')   AS invalid,
                   SUM(status='in_review') AS in_review,
                   SUM(status='duplicate') AS duplicate,
                   SUM(status='unsupported') AS unsupported,
                   SUM(status IN ('queued','processing')) AS processing,
                   COALESCE(SUM(points),0) AS points
            FROM submissions {where}
            GROUP BY user_id
            """,
            params,
        ).fetchall()
    return [
        {
            "user_id": r["user_id"], "total": r["total"], "accepted": r["accepted"] or 0,
            "invalid": r["invalid"] or 0, "in_review": r["in_review"] or 0,
            "duplicate": r["duplicate"] or 0, "unsupported": r["unsupported"] or 0,
            "processing": r["processing"] or 0,
            "points": r["points"] or 0,
        }
        for r in rows
    ]


def count_user_duplicates(user_id: str, dup_kind: str) -> int:
    """Count a user's duplicates of a given kind ('regular' or 'self')."""
    with _connect() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) c FROM submissions WHERE user_id=? AND status='duplicate' AND dup_kind=?",
            (user_id, dup_kind),
        ).fetchone()["c"])


def count_user_regular_duplicates(user_id: str) -> int:
    return count_user_duplicates(user_id, "regular")


def count_user_self_duplicates(user_id: str) -> int:
    return count_user_duplicates(user_id, "self")


def count_user_uploads_since(user_id: str, since_iso: str) -> int:
    with _connect() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) c FROM submissions WHERE user_id=? AND created_at >= ?",
            (user_id, since_iso),
        ).fetchone()["c"])


def find_exact_hash_match(content_hash: str, exclude_id: Optional[int] = None) -> Optional[dict]:
    """O(1) indexed lookup for a TRUE re-upload (identical bytes). Returns the most recent
    prior submission with this sha256, or None. Checked before the fuzzy Hamming scan."""
    if not content_hash:
        return None
    where, params = "content_hash = ?", [content_hash]
    if exclude_id is not None:
        where += " AND id != ?"; params.append(exclude_id)
    with _connect() as conn:
        row = conn.execute(
            f"SELECT * FROM submissions WHERE {where} ORDER BY id DESC LIMIT 1", params,
        ).fetchone()
    return dict(row) if row else None


def find_phash_match(image_hash: str, max_distance: int, limit: int = 5000, exclude_id: Optional[int] = None) -> Optional[dict]:
    """Nearest prior submission within max_distance bits (most recent first). None if no image_hash."""
    if not image_hash:
        return None
    from app.services.imagehash import hamming
    where, params = "image_hash IS NOT NULL", []
    if exclude_id is not None:
        where += " AND id != ?"; params.append(exclude_id)
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM submissions WHERE {where} ORDER BY id DESC LIMIT ?", params,
        ).fetchall()
    best, best_d = None, max_distance + 1
    for r in rows:
        d = hamming(image_hash, r["image_hash"])
        if d <= max_distance and d < best_d:
            best, best_d = dict(r), d
            if d == 0:
                break
    return best


def reconcile_duplicate_captures() -> dict:
    """One-off cleanup: where several ACCEPTED submissions share the same (platform, handle),
    keep the earliest as the legitimate capture and demote the rest to 'duplicate' with 0 points.
    Already-settled or already-invoiced rows are left untouched (they've been billed/paid).
    Idempotent — re-running finds nothing because demoted rows are no longer 'accepted'."""
    ts = _now()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, acct_platform, acct_handle, settled, invoice_id FROM submissions "
            "WHERE status='accepted' AND acct_platform IS NOT NULL AND acct_handle IS NOT NULL "
            "ORDER BY acct_platform, acct_handle, id"
        ).fetchall()
        groups: dict = {}
        for r in rows:
            groups.setdefault((r["acct_platform"], r["acct_handle"]), []).append(r)
        demoted, skipped = [], 0
        dup_groups = 0
        for subs in groups.values():
            if len(subs) < 2:
                continue
            dup_groups += 1
            for r in subs[1:]:  # keep subs[0] (earliest id); demote the rest
                if r["settled"] or r["invoice_id"] is not None:
                    skipped += 1
                    continue
                conn.execute(
                    "UPDATE submissions SET status='duplicate', dup_kind='regular', points=0, updated_at=? WHERE id=?",
                    (ts, r["id"]),
                )
                demoted.append(r["id"])
    return {"duplicateGroups": dup_groups, "demoted": len(demoted), "skipped": skipped}


def reassign_user(old_user_id: str, new_user_id: str) -> int:
    """One-off migration: move legacy submissions to a real user id."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE submissions SET user_id=? WHERE user_id=?", (new_user_id, old_user_id)
        )
        return cur.rowcount


def get_submission_any(submission_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
    return dict(row) if row else None


def update_submission_status(
    submission_id: int, status: str, points: int, analysis_json: Optional[str] = None,
    acct_platform: Optional[str] = None, acct_handle: Optional[str] = None,
    update_acct: bool = False, dup_kind: Optional[str] = None,
    platform: Optional[str] = None, image_hash: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> Optional[dict]:
    sets = ["status=?", "points=?", "updated_at=?"]
    params: list = [status, points, _now()]
    if analysis_json is not None:
        sets.append("analysis_json=?")
        params.append(analysis_json)
    if update_acct:
        sets += ["acct_platform=?", "acct_handle=?"]
        params += [acct_platform, acct_handle]
    if dup_kind is not None:
        sets.append("dup_kind=?")
        params.append(dup_kind)
    if platform is not None:
        sets.append("platform=?"); params.append(platform)
    if image_hash is not None:
        sets.append("image_hash=?"); params.append(image_hash)
    if content_hash is not None:
        sets.append("content_hash=?"); params.append(content_hash)
    params.append(submission_id)
    with _connect() as conn:
        conn.execute(f"UPDATE submissions SET {', '.join(sets)} WHERE id=?", params)
        row = conn.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------- async queue (worker)
def claim_next_queued(worker_id: str) -> Optional[dict]:
    """Atomically claim the oldest 'queued' submission -> 'processing'. Returns it, or None.
    SQLite has a single writer, so the UPDATE...WHERE id=(SELECT...) claim is atomic."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE submissions SET status='processing', worker_id=?, started_at=?, attempts=attempts+1 "
            "WHERE id = (SELECT id FROM submissions WHERE status='queued' ORDER BY id ASC LIMIT 1)",
            (worker_id, _now()),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM submissions WHERE status='processing' AND worker_id=? ORDER BY started_at DESC LIMIT 1",
            (worker_id,),
        ).fetchone()
    return dict(row) if row else None


def requeue_stale(stale_before_iso: str, max_attempts: int) -> tuple[int, int]:
    """Requeue items stuck in 'processing'; park over-attempts as 'in_review'. Returns (requeued, parked)."""
    with _connect() as conn:
        parked = conn.execute(
            "UPDATE submissions SET status='in_review', worker_id=NULL, updated_at=? "
            "WHERE status='processing' AND started_at < ? AND attempts >= ?",
            (_now(), stale_before_iso, max_attempts),
        ).rowcount
        requeued = conn.execute(
            "UPDATE submissions SET status='queued', worker_id=NULL, updated_at=? "
            "WHERE status='processing' AND started_at < ? AND attempts < ?",
            (_now(), stale_before_iso, max_attempts),
        ).rowcount
    return int(requeued), int(parked)


def count_by_status(status: str) -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) c FROM submissions WHERE status=?", (status,)).fetchone()["c"])


# Final states an uploader may contest into the review queue.
# Duplicates are intentionally excluded — a re-capture of an already-accepted account
# has nothing to overturn (the original capture stands).
DISPUTABLE_STATUSES = ("accepted", "invalid")


def dispute_submission(user_id: str, submission_id: int) -> Tuple[Optional[dict], Optional[str]]:
    """Owner contests a decided submission: move it back to the review queue, once only.

    Returns (submission, error) where error is one of:
    None (success) | "not_found" | "not_disputable" | "already_disputed".
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id=? AND user_id=?", (submission_id, user_id)
        ).fetchone()
        if row is None:
            return None, "not_found"
        if int(row["disputed"] or 0) == 1:
            return None, "already_disputed"
        if row["status"] not in DISPUTABLE_STATUSES:
            return None, "not_disputable"
        conn.execute(
            "UPDATE submissions SET status='in_review', disputed=1, updated_at=? WHERE id=?",
            (_now(), submission_id),
        )
        updated = conn.execute(
            "SELECT * FROM submissions WHERE id=?", (submission_id,)
        ).fetchone()
    return dict(updated), None


def list_submissions(
    user_id: str, status: Optional[str], page: int, limit: int
) -> Tuple[List[dict], int]:
    where = "WHERE user_id = ?"
    params: list = [user_id]
    if status == "processing":
        # The UI's "Processing" bucket spans both async-queue states.
        where += " AND status IN ('queued','processing')"
    elif status:
        where += " AND status = ?"
        params.append(status)
    offset = (page - 1) * limit
    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM submissions {where}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM submissions {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows], int(total)


def list_all_submissions(
    status: Optional[str], org_id: Optional[str], african: Optional[str],
    user_ids: Optional[List[str]], page: int, limit: int,
) -> Tuple[List[dict], int]:
    """Admin-wide listing (superuser/turk_admin): filter by status, org, African
    classification (from analysis_json), and an optional set of uploader ids."""
    import json as _json
    if user_ids is not None and not user_ids:
        return [], 0  # a user filter that matched nobody
    where, params = "WHERE 1=1", []
    if status == "processing":
        where += " AND status IN ('queued','processing')"
    elif status:
        where += " AND status = ?"; params.append(status)
    if org_id:
        where += " AND org_id = ?"; params.append(org_id)
    if user_ids is not None:
        where += f" AND user_id IN ({','.join('?' * len(user_ids))})"; params += user_ids
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM submissions {where} ORDER BY id DESC", params
        ).fetchall()]
    if african:
        def _cls(r):
            aj = r.get("analysis_json")
            if not aj:
                return None
            try:
                return _json.loads(aj).get("african_classification")
            except Exception:
                return None
        rows = [r for r in rows if _cls(r) == african]
    total = len(rows)
    start = (page - 1) * limit
    return rows[start:start + limit], total


def get_submission(user_id: str, submission_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ? AND user_id = ?",
            (submission_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def recent_submissions(user_id: str, n: int = 5) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, n),
        ).fetchall()
    return [dict(r) for r in rows]


def dashboard_summary(user_id: str) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, points, updated_at, settled FROM submissions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    total_points = sum(r["points"] for r in rows)
    settled_rows = [r for r in rows if r["settled"]]
    settled_points = sum(r["points"] for r in settled_rows)
    settled_count = len(settled_rows)
    unsettled_points = total_points - settled_points
    accepted = sum(1 for r in rows if r["status"] == "accepted")
    in_review = sum(1 for r in rows if r["status"] == "in_review")
    processed = sum(1 for r in rows if r["status"] == "processed")
    invalid = sum(1 for r in rows if r["status"] == "invalid")
    duplicate = sum(1 for r in rows if r["status"] == "duplicate")
    unsupported = sum(1 for r in rows if r["status"] == "unsupported")
    processing = sum(1 for r in rows if r["status"] in ("queued", "processing"))
    updated_today = sum(1 for r in rows if (r["updated_at"] or "").startswith(today))

    # Per-category point makeup — sums straight from each submission's awarded
    # points so it ALWAYS reconciles exactly to totalPoints. Surfaced to users so
    # they can see where their score comes from (cuts down on "why X points?" disputes).
    accepted_pts = sum(r["points"] for r in rows if r["status"] == "accepted")
    duplicate_pts = sum(r["points"] for r in rows if r["status"] == "duplicate")
    points_breakdown = [
        {"key": "accepted", "label": "Accepted captures", "count": accepted, "points": accepted_pts},
        {"key": "duplicate", "label": "Duplicate penalties", "count": duplicate, "points": duplicate_pts},
        {"key": "processing", "label": "Processing", "count": processing, "points": 0},
        {"key": "in_review", "label": "Pending review", "count": in_review, "points": 0},
        {"key": "invalid", "label": "Rejected / invalid", "count": invalid, "points": 0},
        {"key": "unsupported", "label": "Unsupported", "count": unsupported, "points": 0},
        # Settled points have been paid out, so they're subtracted to leave the outstanding total.
        {"key": "settled", "label": "Settled (paid out)", "count": settled_count, "points": -settled_points},
    ]

    return {
        "totalPoints": total_points,
        "settledPoints": settled_points,
        "unsettledPoints": unsettled_points,
        "totalSubmissions": len(rows),
        "accepted": accepted,
        "inReview": in_review,
        "processed": processed,
        "invalid": invalid,
        "duplicate": duplicate,
        "unsupported": unsupported,
        "processing": processing,
        "updatedToday": updated_today,
        "pointsBreakdown": points_breakdown,
    }


# ------------------------------------------------------------------- invoices
# Point-bearing, final-state submissions are billable; in_review/invalid/unsupported aren't.
INVOICEABLE_STATUSES = ("accepted", "duplicate")
_INV_SQL = "status IN ('accepted','duplicate')"


def outstanding_summary(org_id: str) -> dict:
    """Uninvoiced billable submissions for an org: count + net points."""
    with _connect() as conn:
        r = conn.execute(
            f"SELECT COUNT(*) c, COALESCE(SUM(points),0) p FROM submissions "
            f"WHERE org_id=? AND invoice_id IS NULL AND {_INV_SQL}",
            (org_id,),
        ).fetchone()
    return {"count": int(r["c"]), "points": int(r["p"])}


def create_invoice(org_id: str, created_by) -> Optional[dict]:
    """Bundle all uninvoiced billable submissions for org into a pending invoice."""
    ts = _now()
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT id, points FROM submissions WHERE org_id=? AND invoice_id IS NULL AND {_INV_SQL}",
            (org_id,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if not ids:
            return None
        total = sum(r["points"] for r in rows)
        cur = conn.execute(
            "INSERT INTO invoices (org_id,status,total_points,submission_count,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (org_id, "pending", total, len(ids), str(created_by), ts),
        )
        inv_id = cur.lastrowid
        conn.execute(
            f"UPDATE submissions SET invoice_id=? WHERE id IN ({','.join('?' * len(ids))})",
            (inv_id, *ids),
        )
        inv = conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    return dict(inv)


def list_invoices(org_id: Optional[str] = None) -> List[dict]:
    with _connect() as conn:
        if org_id is None:
            rows = conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM invoices WHERE org_id=? ORDER BY id DESC", (org_id,)).fetchall()
    return [dict(r) for r in rows]


def get_invoice(invoice_id: int) -> Optional[dict]:
    with _connect() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv:
            return None
        items = conn.execute(
            "SELECT id,user_id,platform,acct_handle,status,points,created_at "
            "FROM submissions WHERE invoice_id=? ORDER BY id",
            (invoice_id,),
        ).fetchall()
    d = dict(inv)
    d["items"] = [dict(i) for i in items]
    return d


def settle_invoice(
    invoice_id: int, settled_by, receipt_object_path: Optional[str] = None,
    receipt_amount: Optional[float] = None,
) -> Tuple[Optional[dict], Optional[str]]:
    ts = _now()
    with _connect() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv:
            return None, "not_found"
        if inv["status"] == "settled":
            return None, "already_settled"
        conn.execute(
            "UPDATE invoices SET status='settled', settled_by=?, settled_at=?, "
            "receipt_object_path=?, receipt_amount=? WHERE id=?",
            (str(settled_by), ts, receipt_object_path, receipt_amount, invoice_id),
        )
        conn.execute("UPDATE submissions SET settled=1, settled_at=? WHERE invoice_id=?", (ts, invoice_id))
        updated = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    return dict(updated), None
