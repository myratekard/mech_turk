"""Shared MongoDB client + helpers for the deployed persistence backend.

Used only when settings.use_mongo is true (MONGO_URI configured). Local dev defaults to
SQLite, so importing this module must NOT require a live server — the client connects lazily.
"""
from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient, ReturnDocument

from app.core.config import settings


@lru_cache(maxsize=1)
def _client() -> MongoClient:
    # Short server-selection timeout so misconfig fails fast instead of hanging requests.
    return MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000, tz_aware=False)


def db():
    return _client()[settings.mongo_db]


def next_id(name: str) -> int:
    """Atomic auto-increment integer id (preserves the int ids the API/frontend expect)."""
    doc = db().counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


def clean(doc: dict | None) -> dict | None:
    """Drop Mongo's _id so returned docs match the SQLite shape exactly."""
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc
