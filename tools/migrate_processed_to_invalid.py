"""One-off: relabel legacy 'processed' submissions as 'invalid' (status taxonomy change)."""
import sqlite3
from pathlib import Path

from app.core.config import settings

db = Path(settings.artifact_dir) / "turk.db"
conn = sqlite3.connect(str(db))
n = conn.execute("UPDATE submissions SET status='invalid' WHERE status='processed'").rowcount
conn.commit()
counts = dict(conn.execute("SELECT status, COUNT(*) FROM submissions GROUP BY status").fetchall())
conn.close()
print(f"migrated processed->invalid: {n}")
print(f"status counts: {counts}")
