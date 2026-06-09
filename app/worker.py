# ABOUTME: Background processing worker (run as `python -m app.worker`). Drains 'queued'
# submissions through the verdict pipeline and updates them, with a reaper that recovers items
# left in 'processing' by a crash/deploy. Durable: all state is in the DB, so restarts are safe.
from __future__ import annotations

import os
import socket
import time
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.services import submissions_db
from app.services.processing import process_submission

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _stale_cutoff_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=settings.worker_stale_seconds)).isoformat()


def _reap() -> None:
    try:
        requeued, parked = submissions_db.requeue_stale(_stale_cutoff_iso(), settings.worker_max_attempts)
        if requeued or parked:
            print(f"[worker] reaper: requeued={requeued} parked={parked}", flush=True)
    except Exception as e:
        print(f"[worker] reaper error: {e}", flush=True)


def _process_one() -> bool:
    """Claim and process one queued item. Returns True if one was handled, False if queue empty."""
    row = submissions_db.claim_next_queued(WORKER_ID)
    if not row:
        return False
    sid = row["id"]
    t0 = time.monotonic()
    try:
        res = process_submission(row)
        submissions_db.update_submission_status(
            sid, res["status"], res["points"],
            analysis_json=res.get("analysis_json"),
            acct_platform=res.get("acct_platform"), acct_handle=res.get("acct_handle"),
            update_acct=res.get("update_acct", False), dup_kind=res.get("dup_kind"),
            platform=res.get("platform"), image_hash=res.get("image_hash"),
            content_hash=res.get("content_hash"),
        )
        print(f"[worker] #{sid} -> {res['status']} ({res['points']}) in {(time.monotonic()-t0)*1000:.0f}ms", flush=True)
    except Exception as e:
        # Leave it 'processing'; the reaper will requeue it (attempts++ already happened at claim)
        # or park it as in_review once it has burned max_attempts. Never crashes the loop.
        print(f"[worker] #{sid} FAILED (attempt {row.get('attempts')}): {e}", flush=True)
    return True


def run() -> None:
    try:
        submissions_db.init_db()
    except Exception:
        pass
    print(f"[worker] started {WORKER_ID} | poll={settings.worker_poll_seconds}s "
          f"stale={settings.worker_stale_seconds}s max_attempts={settings.worker_max_attempts}", flush=True)
    _reap()  # recover anything left 'processing' by a previous crash/deploy
    last_reap = time.monotonic()
    reap_every = min(settings.worker_stale_seconds, 60)
    while True:
        if time.monotonic() - last_reap >= reap_every:
            _reap()
            last_reap = time.monotonic()
        try:
            handled = _process_one()
        except Exception as e:
            print(f"[worker] loop error: {e}", flush=True)
            handled = False
        if not handled:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run()
