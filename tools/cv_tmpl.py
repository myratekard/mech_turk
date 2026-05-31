"""CV detector v2: blue-disc localizer + TEMPLATE-MATCH confirmation of the check shape.

Localization (blue, size, roundish) works great; confirming the badge via normalized
cross-correlation against reference badge crops is far more robust than HSV check stats.
"""
import glob
import json
import os

import cv2
import numpy as np
from PIL import Image

TOP_FRAC = 0.55
MIN_DF, MAX_DF = 0.016, 0.08
TMPL_DIR = "badges"
# (file, box, platform) — confirmed verified badges (full-res) to seed templates.
SEEDS = [
    ("IMG_4909.PNG", (607, 220, 46, 46), "instagram"),
    ("IMG_4882.PNG", (586, 609, 50, 50), "x"),
    ("IMG_4970.PNG", (744, 639, 30, 30), "tiktok"),
]


def _bgr(p):
    return cv2.cvtColor(np.array(Image.open(p).convert("RGB")), cv2.COLOR_RGB2BGR)


def _blue(hsv):
    return cv2.inRange(hsv, np.array([90, 90, 90]), np.array([125, 255, 255]))


def extract_templates():
    os.makedirs(TMPL_DIR, exist_ok=True)
    for f, (x, y, w, h), plat in SEEDS:
        img = _bgr(f"verify/samples/_fullres/{f}")
        crop = img[y:y + h, x:x + w]
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (40, 40), interpolation=cv2.INTER_AREA)
        cv2.imwrite(f"{TMPL_DIR}/{plat}.png", g)
    print("templates:", [s[2] for s in SEEDS])


def load_templates():
    t = []
    for p in glob.glob(f"{TMPL_DIR}/*.png"):
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if g is not None:
            t.append(cv2.resize(g, (40, 40)))
    return t


def detect(bgr, templates, thr=0.76):  # 0.76 = clean badge/non-badge split on both domains
    H, W = bgr.shape[:2]
    band = bgr[: int(H * TOP_FRAC), :]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    mask = cv2.morphologyEx(_blue(hsv), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)
    min_d, max_d = MIN_DF * W, MAX_DF * W
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    best = 0.0
    for c in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, w, h = cv2.boundingRect(c)
        if max(w, h) < min_d or max(w, h) > max_d or not (0.6 < w / (h + 1e-6) < 1.6):
            continue
        if cv2.contourArea(c) / (w * h + 1e-6) < 0.45:   # filled-ish (reject rings)
            continue
        # Pad generously, then let the 40px template SLIDE over the patch at several
        # scales -> robust to localization offset + badge-size variation.
        pad = int(max(w, h) * 0.35)
        xa, ya = max(0, x - pad), max(0, y - pad)
        patch = gray[ya:y + h + pad, xa:x + w + pad]
        if patch.size == 0:
            continue
        for scale in (44, 52, 64):
            pr = cv2.resize(patch, (scale, scale))
            for t in templates:
                if pr.shape[0] < t.shape[0]:
                    continue
                best = max(best, float(cv2.matchTemplate(pr, t, cv2.TM_CCOEFF_NORMED).max()))
    return best >= thr, best


def evaluate(thr=0.45):
    templates = load_templates()
    labels = json.load(open("verify/samples/_fullres/_labels.json"))
    rows = []
    for f in sorted(glob.glob("verify/samples/_fullres/*.PNG")):
        name = f.replace("\\", "/").split("/")[-1]
        if name.startswith("_") or "verified" not in labels.get(name, {}):
            continue
        v, s = detect(_bgr(f), templates, thr)
        rows.append((name, labels[name].get("platform"), bool(labels[name]["verified"]), v, s))
    tp = sum(1 for *_, e, v, s in rows if e and v); fn = sum(1 for *_, e, v, s in rows if e and not v)
    fp = sum(1 for *_, e, v, s in rows if not e and v); tn = sum(1 for *_, e, v, s in rows if not e and not v)
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    print(f"thr={thr}  TP={tp} FP={fp} TN={tn} FN={fn}  P={P:.3f} R={R:.3f} F1={(2*P*R/(P+R) if P+R else 0):.3f}")
    return rows


if __name__ == "__main__":
    extract_templates()
    best_rows = None
    for thr in (0.50, 0.55, 0.60, 0.65, 0.70):
        best_rows = evaluate(thr)
    # FP/FN at a chosen threshold for inspection
    print("\n--- mismatches at thr=0.60 ---")
    templates = load_templates()
    labels = json.load(open("verify/samples/_fullres/_labels.json"))
    import glob as _g
    for f in sorted(_g.glob("verify/samples/_fullres/*.PNG")):
        n = f.replace("\\", "/").split("/")[-1]
        if n.startswith("_") or "verified" not in labels.get(n, {}):
            continue
        e = bool(labels[n]["verified"]); v, s = detect(_bgr(f), templates, 0.60)
        if e != v:
            print(f"  {'FP' if v else 'FN'} {labels[n].get('platform'):9} score={s:.2f} {n}")
