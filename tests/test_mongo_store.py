"""Exercise the MongoDB store implementations against an in-memory mongomock server,
so the deployed persistence path is covered without a live MongoDB."""
from __future__ import annotations

import pytest

mongomock = pytest.importorskip("mongomock")

from app.core.config import settings
from app.services import mongo_client
from app.services.store_mongo import auth as mauth
from app.services.store_mongo import submissions as msub


@pytest.fixture
def mongo(monkeypatch):
    client = mongomock.MongoClient()
    monkeypatch.setattr(mongo_client, "_client", lambda: client)
    return client


def _ins(user_id, status, points=0, **kw):
    return msub.insert_submission(
        user_id=user_id, image_url="i", object_path="p", file_name="f.jpeg",
        platform="Instagram", status=status, points=points, analysis_json=None, **kw,
    )


def test_integer_ids_increment(mongo):
    a = _ins("u1", "accepted", 50)
    b = _ins("u1", "invalid", 0)
    assert a["id"] == 1 and b["id"] == 2  # counters preserve sequential int ids


def test_dispute_flow(mongo):
    s = _ins("u1", "invalid")
    assert s["disputed"] == 0
    row, err = msub.dispute_submission("u1", s["id"])
    assert err is None and row["status"] == "in_review" and row["disputed"] == 1
    _, err2 = msub.dispute_submission("u1", s["id"])
    assert err2 == "already_disputed"
    # duplicates can't be disputed
    d = _ins("u1", "duplicate")
    _, err3 = msub.dispute_submission("u1", d["id"])
    assert err3 == "not_disputable"


def test_analytics_and_per_user(mongo):
    for st, pts in [("accepted", 50), ("accepted", 50), ("invalid", 0), ("duplicate", -5)]:
        _ins("u2", st, pts)
    a = msub.analytics(None)
    assert a["accepted"] == 2 and a["invalid"] == 1 and a["duplicate"] == 1 and a["totalPoints"] == 95
    ps = msub.per_user_stats(None)
    u2 = next(r for r in ps if r["user_id"] == "u2")
    assert u2["total"] == 4 and u2["accepted"] == 2 and u2["points"] == 95


def test_duplicate_capture_and_phash(mongo):
    _ins("u3", "accepted", 50, acct_platform="instagram", acct_handle="nasa", image_hash="ffffffffffffffff")
    assert msub.is_duplicate_capture("instagram", "nasa") is True
    assert msub.is_duplicate_capture("instagram", "other") is False
    m = msub.find_phash_match("ffffffffffffffff", 5)
    assert m and m["user_id"] == "u3"


def test_dashboard_summary_breakdown(mongo):
    _ins("u4", "accepted", 50)
    _ins("u4", "duplicate", -5)
    s = msub.dashboard_summary("u4")
    assert s["totalPoints"] == 45 and s["accepted"] == 1
    assert any(b["key"] == "accepted" and b["points"] == 50 for b in s["pointsBreakdown"])


def test_invoice_flow(mongo):
    # Two billable submissions (accepted +50, duplicate -5) + one in_review (not billable).
    _ins("u9", "accepted", 50, org_id="org_a")
    _ins("u9", "duplicate", -5, org_id="org_a")
    _ins("u9", "in_review", 0, org_id="org_a")
    out = msub.outstanding_summary("org_a")
    assert out["count"] == 2 and out["points"] == 45
    inv = msub.create_invoice("org_a", created_by=1)
    assert inv["status"] == "pending" and inv["total_points"] == 45 and inv["submission_count"] == 2
    # Outstanding now empty (those submissions carry the invoice_id).
    assert msub.outstanding_summary("org_a")["count"] == 0
    detail = msub.get_invoice(inv["id"])
    assert len(detail["items"]) == 2
    settled, err = msub.settle_invoice(inv["id"], settled_by=2)
    assert err is None and settled["status"] == "settled"
    _, err2 = msub.settle_invoice(inv["id"], settled_by=2)
    assert err2 == "already_settled"
    # Covered submissions are now marked settled.
    rows, _ = msub.list_submissions("u9", None, 1, 50)
    assert sum(1 for r in rows if r.get("settled")) == 2


def test_auth_no_seed_and_referrals(mongo):
    mauth.init_auth_db()
    # No superuser is seeded anymore — the DB starts empty.
    assert mauth.get_user_by_username(settings.superuser_username) is None
    su = mauth.create_user(
        username="boss", email="boss@x.com", password="x", role="superuser",
        org_id=None, referred_by=None,
    )
    u = mauth.create_clerk_user(
        clerk_id="ck1", username="alice", email="a@x.com", role="user",
        org_id=None, referred_by=su["id"],
    )
    assert u["clerk_id"] == "ck1" and mauth.get_user_by_clerk_id("ck1")["username"] == "alice"
    assert any(r["clerk_id"] == "ck1" for r in mauth.list_referrals(su["id"]))
