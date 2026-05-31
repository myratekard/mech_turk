"""Evaluate the CV detector against the LLM-labeled full-res samples."""
import glob
import json

from tools.cv_lab import detect, _bgr

labels = json.load(open("verify/samples/_fullres/_labels.json"))
rows = []
for f in sorted(glob.glob("verify/samples/_fullres/*.PNG")):
    name = f.replace("\\", "/").split("/")[-1]
    if name.startswith("_"):
        continue
    lab = labels.get(name, {})
    if "verified" not in lab:
        continue
    exp = bool(lab["verified"])
    try:
        v, s, _ = detect(_bgr(f))
    except Exception:
        v, s = False, 0
    rows.append((name, lab.get("platform"), exp, v, s))

tp = sum(1 for *_, e, v, s in rows if e and v)
fn = sum(1 for *_, e, v, s in rows if e and not v)
fp = sum(1 for *_, e, v, s in rows if not e and v)
tn = sum(1 for *_, e, v, s in rows if not e and not v)
prec = tp / (tp + fp) if tp + fp else 0
rec = tp / (tp + fn) if tp + fn else 0
f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
print(f"N={len(rows)}  TP={tp} FP={fp} TN={tn} FN={fn}")
print(f"precision={prec:.3f} recall={rec:.3f} f1={f1:.3f} acc={(tp+tn)/len(rows):.3f}")
print("\nFALSE POSITIVES (CV says badge, LLM says no):")
for n, p, e, v, s in rows:
    if not e and v:
        print(f"  {p:9} {s:.2f}  {n}")
print("\nFALSE NEGATIVES (CV missed a badge LLM found):")
for n, p, e, v, s in rows:
    if e and not v:
        print(f"  {p:9} {s:.2f}  {n}")
