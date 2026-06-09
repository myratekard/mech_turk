from __future__ import annotations

import io
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import cv2

from app.core.config import settings

from app.schemas.models import (
    AnalysisResult,
    Metric,
    ProfileArtifact,
    VisionAnalysis,
)
from app.services import badge_cv, fusion
from app.services.badge_cv import bgr_from_bytes
from app.services.store import ArtifactStore
from app.services.vision_llm import analyze_screenshot


def _downscale_for_llm(image_bytes: bytes, mime: str) -> tuple[bytes, str]:
    """Return a smaller JPEG (longest edge <= llm_image_max_dim) to send to the LLM — faster
    upload/inference and fewer image tokens. Full-res bytes are kept for the CV check. Falls
    back to the original on any error or when already small enough."""
    max_dim = settings.llm_image_max_dim
    if not max_dim:
        return image_bytes, mime
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(image_bytes))
        w, h = im.size
        if max(w, h) <= max_dim:
            return image_bytes, mime
        scale = max_dim / float(max(w, h))
        im = im.convert("RGB").resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return image_bytes, mime


def _build_profile(va: VisionAnalysis) -> ProfileArtifact:
    p = va.profile
    posts = Metric.parse(p.posts) if p.posts is not None else None
    likes = Metric.parse(p.likes) if p.likes is not None else None
    return ProfileArtifact(
        platform=va.platform,
        display_name=p.display_name,
        handle=(p.handle or "").lstrip("@") or None,
        bio=p.bio,
        category=p.category,
        external_links=p.external_links or [],
        followers=Metric.parse(p.followers),
        following=Metric.parse(p.following),
        posts=posts,
        likes=likes,
    )


def analyze(
    image_bytes: bytes,
    mime: str = "image/jpeg",
    store: Optional[ArtifactStore] = None,
    persist: bool = True,
    force_profile: bool = False,
) -> AnalysisResult:
    """Full pipeline: vision LLM -> CV cross-check -> fuse -> (gated) extract -> persist.

    force_profile=True extracts the profile even when the verdict isn't "verified" — used
    when a reviewer overturns a rejection and we need the handle to complete the capture.
    """
    analysis_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []

    # 1) Vision analysis (platform + verdict + fields) in one call — on a downscaled copy
    #    (full-res image_bytes is reserved for the CV check below).
    _t = time.perf_counter()
    llm_bytes, llm_mime = _downscale_for_llm(image_bytes, mime)
    va = analyze_screenshot(llm_bytes, mime=llm_mime)
    llm_ms = (time.perf_counter() - _t) * 1000

    # 2) Independent CV second opinion: template-match the verified tick
    _t = time.perf_counter()
    bgr = bgr_from_bytes(image_bytes)
    cv_signal = badge_cv.detect(bgr)
    cv_ms = (time.perf_counter() - _t) * 1000
    print(f"[timing] pipeline: llm={llm_ms:.0f}ms cv={cv_ms:.0f}ms "
          f"orig={len(image_bytes)} llm_bytes={len(llm_bytes)}", flush=True)

    # 3) Fuse the two signals (lenient policy)
    llm_signal = fusion.to_llm_signal(va)
    verification = fusion.fuse(llm_signal, cv_signal, badge_bbox=va.badge_bbox)

    if cv_signal.method != "unavailable" and llm_signal.is_verified != cv_signal.matched:
        warnings.append(
            f"Signal disagreement: LLM verified={llm_signal.is_verified} "
            f"(conf {llm_signal.confidence}), CV matched={cv_signal.matched} "
            f"(score {cv_signal.score})."
        )
    if va.platform == "unknown":
        warnings.append("Platform could not be confidently identified.")

    # 4) Extraction gate — keep profile when verified (or when forced, e.g. reviewer override)
    profile = _build_profile(va) if (verification.verified or force_profile) else None

    result = AnalysisResult(
        id=analysis_id,
        created_at=created_at,
        platform=va.platform,
        platform_confidence=va.platform_confidence,
        is_profile_screenshot=va.is_profile_screenshot,
        account_type=va.account_type,
        african_classification=va.african_classification,
        african_confidence=va.african_confidence,
        appears_african_descent=(
            True if va.african_classification == "african"
            else False if va.african_classification == "non_african"
            else None
        ),
        verification=verification,
        profile=profile,
        warnings=warnings,
    )

    # 5) Persist artifact + evidence
    if persist:
        store = store or ArtifactStore()
        try:
            result.source_image_ref = store.save_image(analysis_id, image_bytes)
            crop = _badge_crop_png(bgr, va.badge_bbox, cv_signal.box)
            if crop is not None:
                result.badge_crop_ref = store.save_badge_crop(analysis_id, crop)
        except Exception as e:  # evidence is best-effort
            warnings.append(f"Artifact persistence partial: {e}")
        store.save_result(result)

    return result


def _badge_crop_png(bgr, badge_bbox, cv_box) -> Optional[bytes]:
    """Best-effort crop of the badge region (LLM bbox preferred, else CV box)."""
    h, w = bgr.shape[:2]
    box = None
    if badge_bbox and len(badge_bbox) == 4:
        x0, y0, x1, y1 = badge_bbox
        box = [int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)]
    elif cv_box:
        box = cv_box
    if not box:
        return None
    x1, y1, x2, y2 = box
    pad = int(0.4 * max(1, max(x2 - x1, y2 - y1)))
    xa, ya = max(0, x1 - pad), max(0, y1 - pad)
    xb, yb = min(w, x2 + pad), min(h, y2 + pad)
    crop = bgr[ya:yb, xa:xb]
    if crop.size == 0:
        return None
    ok, buf = cv2.imencode(".png", crop)
    return buf.tobytes() if ok else None
