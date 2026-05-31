"""Measure the dominant blue HUE of the best-matching disc for FPs (blue heart) vs real
badges, to decide whether a hue gate can separate them."""
import glob
import cv2
import numpy as np
from tools.cv_tmpl import _bgr, _blue, load_templates, MIN_DF, MAX_DF, TOP_FRAC

TS = load_templates()


def best_candidate_hue(bgr):
    H, W = bgr.shape[:2]
    band = bgr[: int(H * TOP_FRAC), :]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    mask = cv2.morphologyEx(_blue(hsv), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    min_d, max_d = MIN_DF * W, MAX_DF * W
    best_s, best_hue = 0.0, None
    for c in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, w, h = cv2.boundingRect(c)
        if max(w, h) < min_d or max(w, h) > max_d or not (0.6 < w / (h + 1e-6) < 1.6):
            continue
        if cv2.contourArea(c) / (w * h + 1e-6) < 0.45:
            continue
        pad = int(max(w, h) * 0.35)
        patch = gray[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
        sc = 0.0
        for s in (44, 52, 64):
            pr = cv2.resize(patch, (s, s))
            for t in TS:
                sc = max(sc, float(cv2.matchTemplate(pr, t, cv2.TM_CCOEFF_NORMED).max()))
        if sc > best_s:
            cell = hsv[y:y + h, x:x + w]
            bm = _blue(cell)
            hue = float(np.median(cell[..., 0][bm > 0])) if np.count_nonzero(bm) else -1
            best_s, best_hue = sc, hue
    return best_s, best_hue


def show(label, paths):
    for p in paths:
        s, hue = best_candidate_hue(_bgr(p))
        print(f"  {label:22} score={s:.2f} hue={hue:.0f}  {p.split(chr(92))[-1][:38]}")


print("REAL BADGES (full-res verified):")
show("badge", ["verify/samples/_fullres/IMG_4882.PNG", "verify/samples/_fullres/IMG_4909.PNG",
               "verify/samples/_fullres/IMG_4970.PNG", "verify/samples/_fullres/IMG_4933.PNG"])
print("BLUE-HEART FP:")
show("heart-FP", glob.glob("verify/samples/instagram/not_verified/*10.06.25 PM (1)*.jpeg")
     + glob.glob("verify/samples/_fullres/IMG_4910.PNG"))
