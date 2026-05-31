from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyze_router, health_router
from app.api.routes.turk import router as turk_router
from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.referrals import router as referrals_router
from app.services import auth_db, submissions_db

app = FastAPI(title="mech_turk — Verified-Account Artifact Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    submissions_db.init_db()
    auth_db.init_auth_db()  # creates tables + seeds the superuser (adeyehat)
    # Migrate legacy 'dev-user' submissions to the seeded superuser.
    su = auth_db.get_user_by_username(auth_db.settings.superuser_username)
    if su:
        submissions_db.reassign_user("dev-user", str(su["id"]))


# Engine endpoints (direct)
app.include_router(health_router)
app.include_router(analyze_router)

# Frontend contract (artifacts/turk) under /api
app.include_router(turk_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(referrals_router, prefix="/api")
