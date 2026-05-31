"""Score distributions to find a clean separating threshold (badges vs non-badges)."""
import glob
import json
from tools.cv_tmpl import detect, load_templates, _bgr

T = load_templates()


def scores_compressed():
    pos, neg = [], []
    for label, exp in (("verified", True), ("not_verified", False)):
        for f in glob.glob(f"verify/samples/*/{label}/*.jpeg"):
            _, s = detect(_bgr(f), T, thr=0)
            (pos if exp else neg).append((s, f.replace("\\", "/").split("/")[-1]))
    return pos, neg


def scores_fullres():
    labels = json.load(open("verify/samples/_fullres/_labels.json"))
    pos, neg = [], []
    for f in glob.glob("verify/samples/_fullres/*.PNG"):
        n = f.replace("\\", "/").split("/")[-1]
        if n.startswith("_") or "verified" not in labels.get(n, {}):
            continue
        _, s = detect(_bgr(f), T, thr=0)
        (pos if labels[n]["verified"] else neg).append((s, n))
    return pos, neg


for name, fn in (("COMPRESSED", scores_compressed), ("FULL-RES", scores_fullres)):
    pos, neg = fn()
    pos.sort(); neg.sort(reverse=True)
    min_tp = pos[0] if pos else (0, "")
    print(f"\n=== {name} ===")
    print(f"  lowest verified (TP) scores: " + ", ".join(f"{s:.2f}" for s, _ in pos[:5]))
    print(f"  highest non-verified scores: " + ", ".join(f"{s:.2f}" for s, _ in neg[:5]))
    print(f"  --> min badge={min_tp[0]:.2f} ({min_tp[1][:30]}); max non-badge={neg[0][0]:.2f} ({neg[0][1][:30]})")
    gap = min_tp[0] - neg[0][0]
    print(f"  separation gap = {gap:+.2f}  ({'CLEAN' if gap > 0 else 'OVERLAP'})")
