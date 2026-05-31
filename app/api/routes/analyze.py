from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.models import AnalysisResult
from app.services.pipeline import analyze as run_pipeline

router = APIRouter(tags=["Analyze"])


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(file: UploadFile = File(...)):
    mime = file.content_type or "image/jpeg"
    if mime not in settings.allowed_mime:
        raise HTTPException(status_code=400, detail=f"Unsupported content-type: {mime}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        return run_pipeline(data, mime=mime)
    except Exception as e:  # surface engine failures cleanly
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")
