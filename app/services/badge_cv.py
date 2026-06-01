"""Validated CV verified-badge detector (second opinion to the LLM).

Blue-disc localizer + sliding multi-scale normalized cross-correlation against reference
badge templates in `badges/`. Cross-domain validated (full-res + WhatsApp-compressed):
P=R=F1=1.0 at threshold 0.76. See tools/cv_tmpl.py for the iteration/eval harness.
"""
from __future__ import annotations

import glob
import io
from functools import lru_cache
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings
from app.schemas.models import CVSignal

_TOP_FRAC = 0.55
_MIN_DF, _MAX_DF = 0.016, 0.08
_TMPL_SIZE = 40


def bgr_from_bytes(image_bytes: bytes) -> np.ndarray:
    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


@lru_cache(maxsize=1)
def _templates() -> Tuple[np.ndarray, ...]:
    out = []
    for p in glob.glob(f"{settings.badges_dir}/*.png"):
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if g is not None:
            out.append(cv2.resize(g, (_TMPL_SIZE, _TMPL_SIZE)))
    return tuple(out)


def _badge_mask(hsv: np.ndarray) -> np.ndarray:
    """Localize candidate verified-badge discs by colour: blue (IG/X/TikTok individuals),
    gold/amber (X businesses), and grey (X government/officials). The grayscale template
    match is the real precision gate — this just proposes candidates."""
    blue = cv2.inRange(hsv, np.array([90, 90, 90]), np.array([125, 255, 255]))
    gold = cv2.inRange(hsv, np.array([16, 90, 120]), np.array([42, 255, 255]))
    # Grey X badge is a blue-grey, not neutral grey — keep the band tight so generic grey
    # UI elements aren't proposed (that wrecked blue-set precision).
    grey = cv2.inRange(hsv, np.array([95, 22, 90]), np.array([120, 80, 195]))
    return cv2.bitwise_or(cv2.bitwise_or(blue, gold), grey)


def detect(bgr: np.ndarray) -> CVSignal:
    """Return a CVSignal: matched (score >= threshold), score, and pixel box."""
    templates = _templates()
    if not templates:
        return CVSignal(matched=False, score=0.0, method="unavailable", box=None)

    H, W = bgr.shape[:2]
    band = bgr[: int(H * _TOP_FRAC), :]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    mask = cv2.morphologyEx(_badge_mask(hsv), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    min_d, max_d = _MIN_DF * W, _MAX_DF * W

    best, best_box = 0.0, None
    for c in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, w, h = cv2.boundingRect(c)
        if max(w, h) < min_d or max(w, h) > max_d or not (0.6 < w / (h + 1e-6) < 1.6):
            continue
        if cv2.contourArea(c) / (w * h + 1e-6) < 0.45:   # filled disc, not a ring
            continue
        pad = int(max(w, h) * 0.35)
        patch = gray[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
        if patch.size == 0:
            continue
        sc = 0.0
        for s in (44, 52, 64):                            # let template slide @ a few scales
            pr = cv2.resize(patch, (s, s))
            for t in templates:
                sc = max(sc, float(cv2.matchTemplate(pr, t, cv2.TM_CCOEFF_NORMED).max()))
        if sc > best:
            best, best_box = sc, [x, y, x + w, y + h]

    return CVSignal(
        matched=best >= settings.badge_cv_threshold,
        score=round(best, 4),
        method="template",
        box=best_box,
    )
