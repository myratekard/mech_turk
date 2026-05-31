"""Functional check of the pHash dedupe + rate-limit DB helpers (no Clerk auth needed)."""
import glob
from datetime import datetime, timedelta, timezone

from app.services import submissions_db
from app.services.imagehash import average_hash, hamming

submissions_db.init_db()

imgs = sorted(glob.glob("verify/samples/**/*.jpeg", recursive=True))
a = open(imgs[0], "rb").read()
b = open(imgs[1], "rb").read()
ha, ha2, hb = average_hash(a), average_hash(a), average_hash(b)
print(f"same image hamming = {hamming(ha, ha2)} (expect 0)")
print(f"different image hamming = {hamming(ha, hb)} (expect large)")

# Insert a first 'upload' of image A by user 999, then check a re-upload matches it.
submissions_db.insert_submission(
    user_id="999", org_id=None, image_url="/x", object_path="/objects/test_a",
    file_name="a.jpg", platform="TikTok", status="accepted", points=100,
    analysis_json='{"k":1}', acct_platform="tiktok", acct_handle="zzz_costtest",
    image_hash=ha,
)
m = submissions_db.find_phash_match(ha, 5)
print(f"phash match for re-upload of A: {'FOUND id=%s user=%s' % (m['id'], m['user_id']) if m else 'none'}")
print(f"phash match for image B (distinct): {submissions_db.find_phash_match(hb, 5) and 'FOUND' or 'none'}")

since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
print(f"user 999 uploads in last 24h: {submissions_db.count_user_uploads_since('999', since)}")
