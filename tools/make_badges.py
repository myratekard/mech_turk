"""Generate per-platform verified-badge templates (badges/<platform>.png).

For each platform, takes one clean VERIFIED sample, asks the vision model for the
badge bbox, crops it, and saves it as the template the CV verifier uses.

Usage:
  python tools/make_badges.py --instagram <img> --x <img> --tiktok <img>
If a flag is omitted, that platform's template is skipped.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from app.core.config import settings
from app.services.cv_verifier import bgr_from_bytes
from app.services.vision_llm import analyze_screenshot


def make_one(platform: str, image_path: str, out_dir: Path):
    data = Path(image_path).read_bytes()
    va = analyze_screenshot(data, mime="image/jpeg")
    if not va.badge_bbox or len(va.badge_bbox) != 4:
        print(f"[{platform}] no badge bbox returned (is_verified={va.is_verified}); skipping")
        return
    bgr = bgr_from_bytes(data)
    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = va.badge_bbox
    bx0, by0, bx1, by1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
    # Tight crop, small pad to keep the disc edge
    pad = int(0.12 * max(1, max(bx1 - bx0, by1 - by0)))
    crop = bgr[max(0, by0 - pad): min(h, by1 + pad), max(0, bx0 - pad): min(w, bx1 + pad)]
    if crop.size == 0:
        print(f"[{platform}] empty crop; skipping")
        return
    out = out_dir / f"{platform}.png"
    cv2.imwrite(str(out), crop)
    print(f"[{platform}] wrote {out}  ({crop.shape[1]}x{crop.shape[0]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instagram")
    ap.add_argument("--x")
    ap.add_argument("--tiktok")
    ap.add_argument("--out", default=settings.badges_dir)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for platform in ("instagram", "x", "tiktok"):
        img = getattr(args, platform if platform != "x" else "x")
        if img:
            make_one(platform, img, out_dir)


if __name__ == "__main__":
    main()
