"""Submissions store — dispatches to SQLite (local dev) or MongoDB (deployed).

Both backends expose identical function signatures returning plain dicts, so the API
routes stay backend-agnostic. Local dev with no MONGO_URI uses SQLite; set MONGO_URI
(or DB_BACKEND=mongo) to use MongoDB. The SQLite implementation lives in
store_sqlite/submissions.py; the Mongo one in store_mongo/submissions.py.
"""
from app.core.config import settings

if settings.use_mongo:
    from app.services.store_mongo.submissions import *  # noqa: F401,F403
else:
    from app.services.store_sqlite.submissions import *  # noqa: F401,F403
