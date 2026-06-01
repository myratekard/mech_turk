"""SQLite store for auth: organizations, users, invites. Shares artifacts/turk.db."""
from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.services.auth import hash_password

_DB_PATH = Path(settings.artifact_dir) / "turk.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "org"


def init_auth_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                slug        TEXT UNIQUE NOT NULL,
                reg_code    TEXT UNIQUE,
                created_by  INTEGER,
                created_at  TEXT NOT NULL
            )
            """
        )
        # Migration + backfill: org reg_code (admin-registration code).
        ocols = {r["name"] for r in conn.execute("PRAGMA table_info(organizations)").fetchall()}
        if "reg_code" not in ocols:
            conn.execute("ALTER TABLE organizations ADD COLUMN reg_code TEXT")
        for r in conn.execute("SELECT id FROM organizations WHERE reg_code IS NULL").fetchall():
            conn.execute("UPDATE organizations SET reg_code=? WHERE id=?", (_gen_referral_code(), r["id"]))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL,
                org_id        INTEGER,
                referred_by   INTEGER,
                referral_code TEXT UNIQUE NOT NULL,
                blocked       INTEGER NOT NULL DEFAULT 0,
                clerk_id      TEXT UNIQUE,
                created_at    TEXT NOT NULL
            )
            """
        )
        # Migrations: add columns to pre-existing users tables.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "blocked" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0")
        if "clerk_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN clerk_id TEXT")
        if "clerk_org_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN clerk_org_id TEXT")
        if "clerk_org_role" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN clerk_org_role TEXT")
        if "login_count" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN login_count INTEGER NOT NULL DEFAULT 0")
        if "last_session_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN last_session_id TEXT")
        # Superuser-issued platform admin (turk_admin) invitations, matched by email at sign-up.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turk_admin_invites (
                email      TEXT PRIMARY KEY,
                created_at TEXT,
                used_at    TEXT
            )
            """
        )
        # Label mirror for Clerk orgs (Clerk is source of truth; this is for display/listing).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clerk_orgs (
                clerk_org_id TEXT PRIMARY KEY,
                name         TEXT,
                created_at   TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invites (
                token       TEXT PRIMARY KEY,
                kind        TEXT NOT NULL,         -- org_admin | user
                org_id      INTEGER,
                role        TEXT NOT NULL,         -- admin | user
                inviter_id  INTEGER,
                created_at  TEXT NOT NULL,
                used_at     TEXT,
                used_by     INTEGER
            )
            """
        )
    # No superuser is seeded: the superuser is provisioned on the first Clerk sign-in whose
    # email matches SUPERUSER_EMAIL (see app/api/routes/auth.py::clerk_sync).


# --------------------------------------------------------------------- users
def _gen_referral_code() -> str:
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]


def create_user(
    *, username: str, email: Optional[str], password: str, role: str,
    org_id: Optional[int], referred_by: Optional[int],
) -> dict:
    code = _gen_referral_code()
    with _connect() as conn:
        # ensure referral_code unique
        while conn.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            code = _gen_referral_code()
        cur = conn.execute(
            """INSERT INTO users (username,email,password_hash,role,org_id,referred_by,referral_code,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (username, email, hash_password(password), role, org_id, referred_by, code, _now()),
        )
        row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_user_by_username(username: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_clerk_id(clerk_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE clerk_id=?", (clerk_id,)).fetchone()
    return dict(row) if row else None


def count_all_users() -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) c FROM users WHERE clerk_id IS NOT NULL").fetchone()["c"])


def create_clerk_user(
    *, clerk_id: str, username: str, email: Optional[str], role: str,
    org_id: Optional[int], referred_by: Optional[int],
) -> dict:
    """Provision a local user backed by a Clerk identity (no local password)."""
    code = _gen_referral_code()
    base_username = (username or f"user{clerk_id[-6:]}").strip() or "user"
    with _connect() as conn:
        while conn.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            code = _gen_referral_code()
        # Ensure a unique username.
        uname, i = base_username, 1
        while conn.execute("SELECT 1 FROM users WHERE username=?", (uname,)).fetchone():
            i += 1
            uname = f"{base_username}{i}"
        cur = conn.execute(
            """INSERT INTO users (username,email,password_hash,role,org_id,referred_by,referral_code,clerk_id,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (uname, email, "", role, org_id, referred_by, code, clerk_id, _now()),
        )
        row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_users(clerk_org_id: Optional[str] = None) -> List[dict]:
    with _connect() as conn:
        if clerk_org_id is None:
            rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM users WHERE clerk_org_id=? ORDER BY id", (clerk_org_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def set_user_clerk_org(user_id: int, clerk_org_id: Optional[str], clerk_org_role: Optional[str] = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET clerk_org_id=?, clerk_org_role=? WHERE id=?",
            (clerk_org_id, clerk_org_role, user_id),
        )


def list_users_by_role(role: str) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM users WHERE role=? ORDER BY id", (role,)).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------- turk-admin invitations
def add_turk_admin_invite(email: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO turk_admin_invites (email, created_at) VALUES (?, ?) "
            "ON CONFLICT(email) DO UPDATE SET used_at=NULL",
            (email.lower(), _now()),
        )


def is_pending_turk_admin(email: Optional[str]) -> bool:
    if not email:
        return False
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM turk_admin_invites WHERE email=? AND used_at IS NULL", (email.lower(),)
        ).fetchone()
    return row is not None


def mark_turk_admin_invite_used(email: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE turk_admin_invites SET used_at=? WHERE email=?", (_now(), email.lower()))


# ----------------------------------------------------------------- clerk orgs
def upsert_clerk_org(clerk_org_id: str, name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO clerk_orgs (clerk_org_id,name,created_at) VALUES (?,?,?) "
            "ON CONFLICT(clerk_org_id) DO UPDATE SET name=excluded.name",
            (clerk_org_id, name, _now()),
        )


def list_clerk_orgs() -> List[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM clerk_orgs ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_clerk_org(clerk_org_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM clerk_orgs WHERE clerk_org_id=?", (clerk_org_id,)).fetchone()
    return dict(row) if row else None


def set_user_role(user_id: int, role: str) -> Optional[dict]:
    with _connect() as conn:
        conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def set_user_blocked(user_id: int, blocked: bool) -> Optional[dict]:
    with _connect() as conn:
        conn.execute("UPDATE users SET blocked=? WHERE id=?", (1 if blocked else 0, user_id))
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def count_users(clerk_org_id: Optional[str] = None) -> tuple[int, int]:
    """Return (total_users, blocked_users) for a Clerk org (or all if None)."""
    with _connect() as conn:
        if clerk_org_id is None:
            total = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            blocked = conn.execute("SELECT COUNT(*) c FROM users WHERE blocked=1").fetchone()["c"]
        else:
            total = conn.execute("SELECT COUNT(*) c FROM users WHERE clerk_org_id=?", (clerk_org_id,)).fetchone()["c"]
            blocked = conn.execute(
                "SELECT COUNT(*) c FROM users WHERE clerk_org_id=? AND blocked=1", (clerk_org_id,)
            ).fetchone()["c"]
    return int(total), int(blocked)


def list_referrals(user_id: int) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE referred_by=? ORDER BY id", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# -------------------------------------------------------------- organizations
def create_org(name: str, created_by: int) -> dict:
    base = _slugify(name)
    code = _gen_referral_code()
    with _connect() as conn:
        slug, i = base, 1
        while conn.execute("SELECT 1 FROM organizations WHERE slug=?", (slug,)).fetchone():
            i += 1
            slug = f"{base}-{i}"
        while conn.execute("SELECT 1 FROM organizations WHERE reg_code=?", (code,)).fetchone():
            code = _gen_referral_code()
        cur = conn.execute(
            "INSERT INTO organizations (name,slug,reg_code,created_by,created_at) VALUES (?,?,?,?,?)",
            (name, slug, code, created_by, _now()),
        )
        row = conn.execute("SELECT * FROM organizations WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_org(org_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
    return dict(row) if row else None


def get_org_by_reg_code(code: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM organizations WHERE reg_code=?", (code,)).fetchone()
    return dict(row) if row else None


def get_user_by_referral_code(code: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE referral_code=?", (code,)).fetchone()
    return dict(row) if row else None


def list_orgs() -> List[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM organizations ORDER BY id").fetchall()
    return [dict(r) for r in rows]


# Invites are referral-code based now (see auth routes /register?ref=<code>); the
# legacy `invites` table/functions were removed in favor of users.referral_code and
# organizations.reg_code.


def record_login(user_id: int, session_id) -> tuple[int, bool]:
    """Increment login_count when a NEW Clerk session id is seen (refreshes reuse the sid,
    so they don't count). Returns (login_count, is_new_session)."""
    with _connect() as conn:
        row = conn.execute("SELECT login_count, last_session_id FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return 0, False
        count, last = int(row["login_count"] or 0), row["last_session_id"]
        if session_id and session_id != last:
            count += 1
            conn.execute("UPDATE users SET login_count=?, last_session_id=? WHERE id=?", (count, session_id, user_id))
            return count, True
        return count, False
