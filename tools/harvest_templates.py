"""Harvest extra badge templates from confirmed-verified full-res images, to widen the
score margin. For each, we take the disc that best matches existing templates (so it's
badge-like by construction), crop it grayscale 40x40, and save to badges/."""
import glob
import json
import cv2
import numpy as np
from tools.cv_tmpl import _bgr, _blue, load_templates, MIN_DF, MAX_DF, TOP_FRAC

T = load_templates()
labels = json.load(open("verify/samples/_fullres/_labels.json"))

# group verified images by platform
by_plat = {}
for f in sorted(glob.glob("verify/samples/_fullres/*.PNG")):
    n = f.replace("\\", "/").split("/")[-1]
    lab = labels.get(n, {})
    if lab.get("verified"):
        by_plat.setdefault(lab.get("platform"), []).append(f)


def best_disc_crop(bgr):
    H, W = bgr.shape[:2]
    band = bgr[: int(H * TOP_FRAC), :]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    mask = cv2.morphologyEx(_blue(hsv), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    min_d, max_d = MIN_DF * W, MAX_DF * W
    best_s, best_crop = 0.0, None
    for c in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, w, h = cv2.boundingRect(c)
        if max(w, h) < min_d or max(w, h) > max_d or not (0.6 < w / (h + 1e-6) < 1.6):
            continue
        if cv2.contourArea(c) / (w * h + 1e-6) < 0.45:
            continue
        cr = cv2.resize(gray[y:y + h, x:x + w], (40, 40))
        pad = int(max(w, h) * 0.35)
        patch = gray[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
        sc = 0.0
        for s in (44, 52, 64):
            pr = cv2.resize(patch, (s, s))
            for t in T:
                sc = max(sc, float(cv2.matchTemplate(pr, t, cv2.TM_CCOEFF_NORMED).max()))
        if sc > best_s:
            best_s, best_crop = sc, cr
    return best_s, best_crop


added = 0
for plat, files in by_plat.items():
    kept = 0
    for f in files:
        if kept >= 4:
            break
        s, crop = best_disc_crop(_bgr(f))
        if crop is not None and s >= 0.80:  # confidently a badge
            cv2.imwrite(f"badges/{plat}_h{kept}.png", crop)
            kept += 1
            added += 1
    print(f"{plat}: harvested {kept}")
print(f"total extra templates: {added}; badges/ now has {len(glob.glob('badges/*.png'))}")
