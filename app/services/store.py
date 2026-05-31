from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.schemas.models import AnalysisResult


class ArtifactStore:
    """Local-filesystem artifact store.

    Writes one JSON record per analysis plus the source image and badge crop as
    evidence. Designed behind a small surface so an R2/Mongo backend (as used by
    myratekard-ai) can replace it later without touching callers.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base = Path(base_dir or settings.artifact_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def save_image(self, analysis_id: str, image_bytes: bytes, ext: str = "jpg") -> str:
        path = self.base / f"{analysis_id}_source.{ext}"
        path.write_bytes(image_bytes)
        return str(path)

    def save_badge_crop(self, analysis_id: str, crop_png: bytes) -> str:
        path = self.base / f"{analysis_id}_badge.png"
        path.write_bytes(crop_png)
        return str(path)

    def save_result(self, result: AnalysisResult) -> str:
        path = self.base / f"{result.id}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return str(path)
