"""Auth store (users, clerk orgs, invites) — dispatches to SQLite or MongoDB.

Local dev with no MONGO_URI uses SQLite; set MONGO_URI (or DB_BACKEND=mongo) to use
MongoDB. SQLite lives in store_sqlite/auth.py; Mongo in store_mongo/auth.py.
"""
from app.core.config import settings

if settings.use_mongo:
    from app.services.store_mongo.auth import *  # noqa: F401,F403
else:
    from app.services.store_sqlite.auth import *  # noqa: F401,F403
