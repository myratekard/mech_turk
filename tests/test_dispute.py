"""Dispute flow: a decided submission can be contested back into review, once only."""
from __future__ import annotations

import uuid

from app.services import submissions_db


def _insert(user_id, status):
    return submissions_db.insert_submission(
        user_id=user_id, image_url="u", object_path="p", file_name="f.jpeg",
        platform="Instagram", status=status, points=0, analysis_json=None,
    )


def test_dispute_decided_submission_routes_to_review_once():
    uid = f"test-{uuid.uuid4()}"
    submissions_db.init_db()
    sub = _insert(uid, "invalid")

    row, err = submissions_db.dispute_submission(uid, sub["id"])
    assert err is None
    assert row["status"] == "in_review"
    assert int(row["disputed"]) == 1

    # Second attempt is rejected.
    row2, err2 = submissions_db.dispute_submission(uid, sub["id"])
    assert row2 is None
    assert err2 == "already_disputed"


def test_dispute_in_review_is_not_disputable():
    uid = f"test-{uuid.uuid4()}"
    submissions_db.init_db()
    sub = _insert(uid, "in_review")
    row, err = submissions_db.dispute_submission(uid, sub["id"])
    assert row is None
    assert err == "not_disputable"


def test_dispute_duplicate_is_not_disputable():
    uid = f"test-{uuid.uuid4()}"
    submissions_db.init_db()
    sub = _insert(uid, "duplicate")
    row, err = submissions_db.dispute_submission(uid, sub["id"])
    assert row is None
    assert err == "not_disputable"


def test_dispute_other_users_submission_not_found():
    uid = f"test-{uuid.uuid4()}"
    submissions_db.init_db()
    sub = _insert(uid, "accepted")
    row, err = submissions_db.dispute_submission(f"other-{uuid.uuid4()}", sub["id"])
    assert row is None
    assert err == "not_found"
