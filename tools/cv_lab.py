"""From-scratch verified-badge CV detector + evaluation harness.

Detector idea (no LLM): in the top band of a profile screenshot, a verified badge is a
small, near-circular, FILLED blue/cyan disc with a WHITE CHECK inside it, sitting on the
name/handle line. We find blue discs, then require a centered white mark inside — which
rejects blue emoji (solid, no inner white), LIVE rings (annular/large), and Follow
buttons (large/rectangular).

Run:  python -m tools.cv_lab          # eval over verify/samples
      python -m tools.cv_lab <img>   # debug one image
"""
from __future__ import annotations

import glob
import sys
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

TOP_FRAC = 0.50          # search only the top half (name/handle area)
MIN_DIAM_FRAC = 0.018    # badge diameter >= 1.8% of image width
MAX_DIAM_FRAC = 0.075    # ... and <= 7.5%


@dataclass
class Hit:
    score: float
    box: tuple
    white_ratio: float
    blue_ratio: float
    circularity: float


def _bgr(path: str) -> np.ndarray:
    img = np.array(Image.open(path).convert("RGB"))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def _blue_mask(hsv: np.ndarray) -> np.ndarray:
    # Brand blues (IG #0095F6 / X #1D9BF0) and TikTok's blue-cyan badge.
    m = cv2.inRange(hsv, np.array([90, 90, 90]), np.array([125, 255, 255]))
    return m


def detect(bgr: np.ndarray, debug: bool = False):
    H, W = bgr.shape[:2]
    band = bgr[: int(H * TOP_FRAC), :]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    mask = _blue_mask(hsv)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

    min_d, max_d = MIN_DIAM_FRAC * W, MAX_DIAM_FRAC * W
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hits: list[Hit] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 30:
            continue
        x, y, w, h = cv2.boundingRect(c)
        diam = max(w, h)
        if diam < min_d or diam > max_d:
            continue
        if not (0.7 < w / (h + 1e-6) < 1.45):
            continue
        peri = cv2.arcLength(c, True)
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        if circularity < 0.6:           # filled disc, not a ring/blob
            continue
        fill = area / (w * h + 1e-6)
        if fill < 0.55:                 # reject annular LIVE rings
            continue
        # White check inside the disc bbox.
        cell = band[y:y + h, x:x + w]
        chsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
        # The check is brighter + LESS saturated than the surrounding blue (anti-aliased
        # to light-blue on small/compressed badges), so use a saturation-based test.
        white = cv2.inRange(chsv, np.array([0, 0, 150]), np.array([179, 120, 255]))
        blue = _blue_mask(chsv)
        wr = float(np.count_nonzero(white)) / (white.size + 1e-6)
        br = float(np.count_nonzero(blue)) / (blue.size + 1e-6)
        if br < 0.30:                   # disc must be mostly blue
            continue
        if not (0.03 < wr < 0.6):       # a check mark, not solid (emoji) nor mostly white
            continue
        score = min(1.0, circularity) * 0.4 + min(br / 0.6, 1.0) * 0.3 + min(wr / 0.2, 1.0) * 0.3
        hits.append(Hit(score, (x, y, x + w, y + h), wr, br, circularity))

    hits.sort(key=lambda h: h.score, reverse=True)
    verified = len(hits) > 0
    if debug:
        return verified, hits, mask
    return verified, (hits[0].score if hits else 0.0), (hits[0].box if hits else None)


def evaluate():
    rows = []
    for label, exp in (("verified", True), ("not_verified", False)):
        for p in glob.glob(f"verify/samples/**/{label}/*.jpeg", recursive=True):
            plat = p.replace("\\", "/").split("/")[-3]
            try:
                v, score, _ = detect(_bgr(p))
            except Exception as e:
                v, score = False, -1.0
            rows.append((plat, exp, v, score, p))

    tp = sum(1 for _, e, v, *_ in rows if e and v)
    fn = sum(1 for _, e, v, *_ in rows if e and not v)
    fp = sum(1 for _, e, v, *_ in rows if not e and v)
    tn = sum(1 for _, e, v, *_ in rows if not e and not v)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    print(f"N={len(rows)}  TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"precision={prec:.3f} recall={rec:.3f} f1={f1:.3f} acc={(tp+tn)/len(rows):.3f}")
    print("\nFALSE POSITIVES (said verified, isn't):")
    for plat, e, v, s, p in rows:
        if not e and v:
            print(f"  {plat:9} {s:.2f}  {p.split('/')[-1][:45]}")
    print("\nFALSE NEGATIVES (missed a real badge):")
    for plat, e, v, s, p in rows:
        if e and not v:
            print(f"  {plat:9} {s:.2f}  {p.split('/')[-1][:45]}")


def diagnose(path: str):
    bgr = _bgr(path)
    H, W = bgr.shape[:2]
    print(f"image {W}x{H}  min_d={MIN_DIAM_FRAC*W:.0f} max_d={MAX_DIAM_FRAC*W:.0f}")
    band = bgr[: int(H * TOP_FRAC), :]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    mask = cv2.morphologyEx(_blue_mask(hsv), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cand = []
    for c in contours:
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        if area < 15 or max(w, h) < 6:
            continue
        peri = cv2.arcLength(c, True)
        circ = 4 * np.pi * area / (peri * peri + 1e-6)
        fill = area / (w * h + 1e-6)
        cell = band[y:y + h, x:x + w]
        chsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
        blue = _blue_mask(chsv)
        wr = np.count_nonzero(cv2.inRange(chsv, np.array([0, 0, 150]), np.array([179, 120, 255]))) / cell[..., 0].size
        br = np.count_nonzero(blue) / cell[..., 0].size
        bright = chsv[..., 2] >= 140
        nonblue_bright = np.count_nonzero(bright & (blue == 0)) / cell[..., 0].size
        cand.append((max(w, h), area, circ, fill, wr, br, nonblue_bright, (x, y, w, h)))
    cand.sort(reverse=True)
    print(f"{len(cand)} blue blobs (diam>=6). top by size:")
    for diam, area, circ, fill, wr, br, nbb, box in cand[:12]:
        print(f"  diam={diam:3d} circ={circ:.2f} fill={fill:.2f} white={wr:.2f} blue={br:.2f} nbBright={nbb:.2f} box={box}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        diagnose(sys.argv[1])
    else:
        evaluate()
