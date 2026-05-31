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
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO submissions
                (user_id, org_id, image_url, object_path, file_name, platform, status, points,
                 analysis_json, acct_platform, acct_handle, image_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, org_id, image_url, object_path, file_name, platform, status, points,
             analysis_json, acct_platform, acct_handle, image_hash, ts, ts),
        )
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


# --------------------------------------------------------------- review queue
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
    """True if an ACCEPTED submission for the same (platform, handle) already exists."""
    if not acct_platform or not acct_handle:
        return False
    q = "SELECT COUNT(*) c FROM submissions WHERE status='accepted' AND acct_platform=? AND acct_handle=?"
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
        rows = conn.execute(f"SELECT status, points FROM submissions {where}", params).fetchall()
    return {
        "totalSubmissions": len(rows),
        "accepted": sum(1 for r in rows if r["status"] == "accepted"),
        "invalid": sum(1 for r in rows if r["status"] == "invalid"),
        "inReview": sum(1 for r in rows if r["status"] == "in_review"),
        "duplicate": sum(1 for r in rows if r["status"] == "duplicate"),
        "totalPoints": sum(r["points"] for r in rows),
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
            "duplicate": r["duplicate"] or 0, "points": r["points"] or 0,
        }
        for r in rows
    ]


def count_user_uploads_since(user_id: str, since_iso: str) -> int:
    with _connect() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) c FROM submissions WHERE user_id=? AND created_at >= ?",
            (user_id, since_iso),
        ).fetchone()["c"])


def find_phash_match(image_hash: str, max_distance: int, limit: int = 5000) -> Optional[dict]:
    """Nearest prior submission within max_distance bits (most recent first). None if no image_hash."""
    if not image_hash:
        return None
    from app.services.imagehash import hamming
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE image_hash IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    best, best_d = None, max_distance + 1
    for r in rows:
        d = hamming(image_hash, r["image_hash"])
        if d <= max_distance and d < best_d:
            best, best_d = dict(r), d
            if d == 0:
                break
    return best


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
    update_acct: bool = False,
) -> Optional[dict]:
    sets = ["status=?", "points=?", "updated_at=?"]
    params: list = [status, points, _now()]
    if analysis_json is not None:
        sets.append("analysis_json=?")
        params.append(analysis_json)
    if update_acct:
        sets += ["acct_platform=?", "acct_handle=?"]
        params += [acct_platform, acct_handle]
    params.append(submission_id)
    with _connect() as conn:
        conn.execute(f"UPDATE submissions SET {', '.join(sets)} WHERE id=?", params)
        row = conn.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
    return dict(row) if row else None


def list_submissions(
    user_id: str, status: Optional[str], page: int, limit: int
) -> Tuple[List[dict], int]:
    where = "WHERE user_id = ?"
    params: list = [user_id]
    if status:
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
            "SELECT status, points, updated_at FROM submissions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    total_points = sum(r["points"] for r in rows)
    accepted = sum(1 for r in rows if r["status"] == "accepted")
    in_review = sum(1 for r in rows if r["status"] == "in_review")
    processed = sum(1 for r in rows if r["status"] == "processed")
    invalid = sum(1 for r in rows if r["status"] == "invalid")
    duplicate = sum(1 for r in rows if r["status"] == "duplicate")
    updated_today = sum(1 for r in rows if (r["updated_at"] or "").startswith(today))
    return {
        "totalPoints": total_points,
        "totalSubmissions": len(rows),
        "accepted": accepted,
        "inReview": in_review,
        "processed": processed,
        "invalid": invalid,
        "duplicate": duplicate,
        "updatedToday": updated_today,
    }
