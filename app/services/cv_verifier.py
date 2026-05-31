from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings
from app.schemas.models import CVSignal

# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def bgr_from_bytes(image_bytes: bytes) -> np.ndarray:
    import io

    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def _crop_from_norm_bbox(
    bgr: np.ndarray, bbox: List[float], pad_frac: float = 0.6
) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Crop a padded region around a normalized [x0,y0,x1,y1] bbox. Returns (crop, (ox, oy))."""
    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = bbox
    px0, py0, px1, py1 = x0 * w, y0 * h, x1 * w, y1 * h
    bw, bh = max(1.0, px1 - px0), max(1.0, py1 - py0)
    pad_x, pad_y = bw * pad_frac, bh * pad_frac
    xa = int(max(0, px0 - pad_x))
    ya = int(max(0, py0 - pad_y))
    xb = int(min(w, px1 + pad_x))
    yb = int(min(h, py1 + pad_y))
    return bgr[ya:yb, xa:xb], (xa, ya)


def _top_band(bgr: np.ndarray, frac: float = 0.45) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Fallback search region: the top `frac` of the screenshot (where name/handle live)."""
    h = bgr.shape[0]
    yb = int(h * frac)
    return bgr[0:yb, :], (0, 0)


# ---------------------------------------------------------------------------
# Heuristic: blue circular badge + white checkmark  (condensed from verify.py)
# ---------------------------------------------------------------------------

def _blue_badge_candidates(bgr: np.ndarray, min_diam: int = 10) -> List[Tuple[int, int, int, int]]:
    max_diam = int(max(bgr.shape[:2]) * 0.5) or min_diam + 1
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.bitwise_or(
        cv2.inRange(hsv, np.array([100, 70, 40]), np.array([130, 255, 255])),
        cv2.inRange(hsv, np.array([90, 60, 40]), np.array([140, 255, 255])),
    )
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 12:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        diam = max(w, h)
        if diam < min_diam or diam > max_diam:
            continue
        perim = cv2.arcLength(cnt, True)
        if perim == 0:
            continue
        circularity = 4 * np.pi * (area / (perim * perim))
        if circularity > 0.5 and 0.5 < (w / (h + 1e-6)) < 1.6:
            boxes.append((x, y, x + w, y + h))
    return boxes


def _looks_like_check(roi_bgr: np.ndarray) -> float:
    if roi_bgr.size == 0 or min(roi_bgr.shape[:2]) < 6:
        return 0.0
    # White (check stroke) sitting inside a blue field is the key signal.
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, np.array([0, 0, 190]), np.array([179, 70, 255]))
    blue = cv2.inRange(hsv, np.array([95, 60, 40]), np.array([135, 255, 255]))
    white_ratio = float(np.count_nonzero(white)) / (white.size + 1e-6)
    blue_ratio = float(np.count_nonzero(blue)) / (blue.size + 1e-6)
    if blue_ratio < 0.10 or white_ratio < 0.02:
        return 0.0
    # A real badge: a healthy blue disc with a modest white check inside it.
    score = min(blue_ratio / 0.35, 1.0) * 0.6 + min(white_ratio / 0.12, 1.0) * 0.4
    return float(np.clip(score, 0.0, 1.0))


def _heuristic_check(region: np.ndarray) -> Tuple[bool, float, Optional[Tuple[int, int, int, int]]]:
    best_score, best_box = 0.0, None
    for (x1, y1, x2, y2) in _blue_badge_candidates(region):
        pad = int(0.2 * max(x2 - x1, y2 - y1))
        xa, ya = max(0, x1 - pad), max(0, y1 - pad)
        xb, yb = min(region.shape[1], x2 + pad), min(region.shape[0], y2 + pad)
        score = _looks_like_check(region[ya:yb, xa:xb])
        if score > best_score:
            best_score, best_box = score, (x1, y1, x2, y2)
    return best_score >= 0.45, best_score, best_box


# ---------------------------------------------------------------------------
# Template matching (per-platform badge image)
# ---------------------------------------------------------------------------

def _template_match(
    region: np.ndarray,
    template_bgr: np.ndarray,
    scales=(0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5),
) -> Tuple[float, Optional[Tuple[int, int, int, int]]]:
    hI, wI = region.shape[:2]
    best_score, best_box = 0.0, None
    for s in scales:
        th, tw = template_bgr.shape[:2]
        ths, tws = int(th * s), int(tw * s)
        if ths < 6 or tws < 6 or ths >= hI or tws >= wI:
            continue
        templ = cv2.resize(template_bgr, (tws, ths), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(region, templ, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best_score:
            best_score = float(max_val)
            best_box = (max_loc[0], max_loc[1], max_loc[0] + tws, max_loc[1] + ths)
    return best_score, best_box


def _load_template(platform: str) -> Optional[np.ndarray]:
    p = Path(settings.badges_dir) / f"{platform}.png"
    if not p.exists():
        return None
    img = np.array(Image.open(p).convert("RGB"))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def verify_badge_cv(
    bgr: np.ndarray,
    platform: str,
    badge_bbox: Optional[List[float]] = None,
) -> CVSignal:
    """Independent CV confirmation that a verified tick is present.

    Searches the LLM-provided badge region (preferred) or the top band of the
    screenshot, using a per-platform template match plus a blue-disc+check heuristic.
    """
    if badge_bbox and len(badge_bbox) == 4:
        region, (ox, oy) = _crop_from_norm_bbox(bgr, badge_bbox)
        # Guard against a degenerate / tiny crop.
        if region.size == 0 or min(region.shape[:2]) < 8:
            region, (ox, oy) = _top_band(bgr)
    else:
        region, (ox, oy) = _top_band(bgr)

    # 1) Template match (if we have a template for this platform). This is the
    #    ONLY signal allowed to assert matched=True — it checks the actual badge
    #    shape, so it is precise enough to corroborate the LLM.
    tmpl = _load_template(platform) if platform in settings.platforms else None
    tm_score, tm_box = (0.0, None)
    if tmpl is not None:
        tm_score, tm_box = _template_match(region, tmpl)
    tm_hit = tm_score >= settings.cv_match_threshold

    # 2) Heuristic (blue disc + white check). Measured precision of this signal on
    #    its own is ~0 (it fires on blue emojis, LIVE rings, Follow buttons), so it
    #    is reported for audit/locating ONLY and must NOT set matched=True.
    heur_hit, heur_score, heur_box = _heuristic_check(region)

    if tm_hit:
        return CVSignal(
            matched=True, score=round(tm_score, 4), method="template",
            box=_abs_box(tm_box, ox, oy),
        )

    # No trustworthy template match. Surface the heuristic only as a soft hint.
    return CVSignal(
        matched=False,
        score=round(max(tm_score, heur_score), 4),
        method="heuristic" if heur_score >= tm_score else "template",
        box=_abs_box(heur_box if heur_score >= tm_score else tm_box, ox, oy),
    )


def _abs_box(box, ox: int, oy: int):
    if box is None:
        return None
    x1, y1, x2, y2 = box
    return [int(x1 + ox), int(y1 + oy), int(x2 + ox), int(y2 + oy)]
