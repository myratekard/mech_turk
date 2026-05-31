from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "model": settings.gemini_model,
        "platforms": list(settings.platforms),
        "gemini_key_configured": bool(settings.google_api_key),
    }
