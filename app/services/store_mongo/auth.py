"""MongoDB implementation of the auth store (users, clerk orgs, invites, legacy orgs).

Mirrors store_sqlite/auth.py — same signatures, same dict shapes, integer ids via the
counters collection. Used when settings.use_mongo is true.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from pymongo import ASCENDING

from app.core.config import settings
from app.services.auth import hash_password
from app.services.mongo_client import clean, col, next_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _users():
    return col("users")


def _orgs():
    return col("organizations")


def _clerk_orgs():
    return col("clerk_orgs")


def _invites():
    return col("turk_admin_invites")


def _org_admin_invites():
    return col("pending_org_admins")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "org"


def _gen_referral_code() -> str:
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]


def init_auth_db() -> None:
    u = _users()
    u.create_index("id", unique=True)
    u.create_index("username", unique=True)
    u.create_index("referral_code", unique=True)
    u.create_index("clerk_id", unique=True, sparse=True)
    u.create_index("clerk_org_id")
    u.create_index("referred_by")
    _clerk_orgs().create_index("clerk_org_id", unique=True)
    _invites().create_index("email", unique=True)
    _orgs().create_index("reg_code", unique=True, sparse=True)
    _orgs().create_index("slug", unique=True, sparse=True)
    # No superuser is seeded: the superuser is provisioned on the first Clerk sign-in whose
    # email matches SUPERUSER_EMAIL (see app/api/routes/auth.py::clerk_sync).


def _unique_referral_code() -> str:
    code = _gen_referral_code()
    while _users().find_one({"referral_code": code}):
        code = _gen_referral_code()
    return code


def _base_user_doc(*, username, email, password_hash, role, org_id, referred_by, referral_code,
                   clerk_id=None) -> dict:
    return {
        "id": next_id("users"),
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "role": role,
        "org_id": org_id,
        "referred_by": referred_by,
        "referral_code": referral_code,
        "blocked": 0,
        "clerk_id": clerk_id,
        "clerk_org_id": None,
        "clerk_org_role": None,
        "login_count": 0,
        "last_session_id": None,
        "created_at": _now(),
    }


def create_user(
    *, username: str, email: Optional[str], password: str, role: str,
    org_id: Optional[int], referred_by: Optional[int],
) -> dict:
    doc = _base_user_doc(
        username=username, email=email, password_hash=hash_password(password), role=role,
        org_id=org_id, referred_by=referred_by, referral_code=_unique_referral_code(),
    )
    _users().insert_one(doc)
    return clean(doc)


def get_user_by_username(username: str) -> Optional[dict]:
    return _users().find_one({"username": username}, {"_id": 0})


def get_user_by_id(user_id: int) -> Optional[dict]:
    return _users().find_one({"id": user_id}, {"_id": 0})


def get_user_by_clerk_id(clerk_id: str) -> Optional[dict]:
    return _users().find_one({"clerk_id": clerk_id}, {"_id": 0})


def count_all_users() -> int:
    return int(_users().count_documents({"clerk_id": {"$ne": None}}))


def create_clerk_user(
    *, clerk_id: str, username: str, email: Optional[str], role: str,
    org_id: Optional[int], referred_by: Optional[int],
) -> dict:
    base_username = (username or f"user{clerk_id[-6:]}").strip() or "user"
    uname, i = base_username, 1
    while _users().find_one({"username": uname}):
        i += 1
        uname = f"{base_username}{i}"
    doc = _base_user_doc(
        username=uname, email=email, password_hash="", role=role, org_id=org_id,
        referred_by=referred_by, referral_code=_unique_referral_code(), clerk_id=clerk_id,
    )
    _users().insert_one(doc)
    return clean(doc)


def list_users(clerk_org_id: Optional[str] = None) -> List[dict]:
    q = {} if clerk_org_id is None else {"clerk_org_id": clerk_org_id}
    return list(_users().find(q, {"_id": 0}).sort("id", ASCENDING))


def set_user_clerk_org(user_id: int, clerk_org_id: Optional[str], clerk_org_role: Optional[str] = None) -> None:
    _users().update_one(
        {"id": user_id}, {"$set": {"clerk_org_id": clerk_org_id, "clerk_org_role": clerk_org_role}}
    )


def list_users_by_role(role: str) -> List[dict]:
    return list(_users().find({"role": role}, {"_id": 0}).sort("id", ASCENDING))


# ----------------------------------------------------- turk-admin invitations
def add_turk_admin_invite(email: str) -> None:
    _invites().update_one(
        {"email": email.lower()},
        {"$set": {"used_at": None}, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )


def is_pending_turk_admin(email: Optional[str]) -> bool:
    if not email:
        return False
    return _invites().find_one({"email": email.lower(), "used_at": None}) is not None


def mark_turk_admin_invite_used(email: str) -> None:
    _invites().update_one({"email": email.lower()}, {"$set": {"used_at": _now()}})


def add_pending_org_admin(email: str, clerk_org_id: str) -> None:
    _org_admin_invites().update_one(
        {"email": email.lower()},
        {"$set": {"clerk_org_id": clerk_org_id, "used_at": None}, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )


def get_pending_org_admin(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    doc = _org_admin_invites().find_one({"email": email.lower(), "used_at": None})
    return doc["clerk_org_id"] if doc else None


def mark_org_admin_invite_used(email: str) -> None:
    _org_admin_invites().update_one({"email": email.lower()}, {"$set": {"used_at": _now()}})


# ----------------------------------------------------------------- clerk orgs
def upsert_clerk_org(clerk_org_id: str, name: str) -> None:
    _clerk_orgs().update_one(
        {"clerk_org_id": clerk_org_id},
        {"$set": {"name": name}, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )


def list_clerk_orgs() -> List[dict]:
    return list(_clerk_orgs().find({}, {"_id": 0}).sort("created_at", -1))


def delete_clerk_org(clerk_org_id: str) -> None:
    _clerk_orgs().delete_one({"clerk_org_id": clerk_org_id})
    _org_admin_invites().delete_many({"clerk_org_id": clerk_org_id})
    _users().update_many(
        {"clerk_org_id": clerk_org_id},
        {"$set": {"clerk_org_id": None, "clerk_org_role": None}},
    )


def get_clerk_org(clerk_org_id: str) -> Optional[dict]:
    return _clerk_orgs().find_one({"clerk_org_id": clerk_org_id}, {"_id": 0})


def set_user_role(user_id: int, role: str) -> Optional[dict]:
    _users().update_one({"id": user_id}, {"$set": {"role": role}})
    return get_user_by_id(user_id)


def set_user_blocked(user_id: int, blocked: bool) -> Optional[dict]:
    _users().update_one({"id": user_id}, {"$set": {"blocked": 1 if blocked else 0}})
    return get_user_by_id(user_id)


def count_users(clerk_org_id: Optional[str] = None) -> tuple[int, int]:
    base = {} if clerk_org_id is None else {"clerk_org_id": clerk_org_id}
    total = _users().count_documents(base)
    blocked = _users().count_documents({**base, "blocked": 1})
    return int(total), int(blocked)


def list_referrals(user_id: int) -> List[dict]:
    return list(_users().find({"referred_by": user_id}, {"_id": 0}).sort("id", ASCENDING))


# -------------------------------------------------------------- organizations (legacy)
def create_org(name: str, created_by: int) -> dict:
    base = _slugify(name)
    slug, i = base, 1
    while _orgs().find_one({"slug": slug}):
        i += 1
        slug = f"{base}-{i}"
    code = _gen_referral_code()
    while _orgs().find_one({"reg_code": code}):
        code = _gen_referral_code()
    doc = {
        "id": next_id("organizations"),
        "name": name, "slug": slug, "reg_code": code,
        "created_by": created_by, "created_at": _now(),
    }
    _orgs().insert_one(doc)
    return clean(doc)


def get_org(org_id: int) -> Optional[dict]:
    return _orgs().find_one({"id": org_id}, {"_id": 0})


def get_org_by_reg_code(code: str) -> Optional[dict]:
    return _orgs().find_one({"reg_code": code}, {"_id": 0})


def get_user_by_referral_code(code: str) -> Optional[dict]:
    return _users().find_one({"referral_code": code}, {"_id": 0})


def list_orgs() -> List[dict]:
    return list(_orgs().find({}, {"_id": 0}).sort("id", ASCENDING))


def record_login(user_id: int, session_id) -> tuple[int, bool]:
    """Increment login_count on a NEW Clerk session id (refreshes reuse the sid)."""
    u = _users().find_one({"id": user_id})
    if not u:
        return 0, False
    count, last = int(u.get("login_count") or 0), u.get("last_session_id")
    if session_id and session_id != last:
        count += 1
        _users().update_one({"id": user_id}, {"$set": {"login_count": count, "last_session_id": session_id}})
        return count, True
    return count, False
