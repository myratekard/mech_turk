"""Cross-domain test: full-res templates (from cv_tmpl) -> tested on the WhatsApp-COMPRESSED
labeled set (independent labels via folder names). No leakage: templates came from full-res.
"""
import glob

from tools.cv_tmpl import detect, load_templates, _bgr

templates = load_templates()


def evaluate(thr):
    rows = []
    for label, exp in (("verified", True), ("not_verified", False)):
        for f in glob.glob(f"verify/samples/*/{label}/*.jpeg"):
            plat = f.replace("\\", "/").split("/")[-3]
            try:
                v, s = detect(_bgr(f), templates, thr)
            except Exception:
                v, s = False, 0.0
            rows.append((plat, exp, v, s, f.replace("\\", "/").split("/")[-1]))
    tp = sum(1 for _, e, v, s, _ in rows if e and v); fn = sum(1 for _, e, v, s, _ in rows if e and not v)
    fp = sum(1 for _, e, v, s, _ in rows if not e and v); tn = sum(1 for _, e, v, s, _ in rows if not e and not v)
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    F = 2 * P * R / (P + R) if P + R else 0
    print(f"thr={thr}  N={len(rows)} TP={tp} FP={fp} TN={tn} FN={fn}  P={P:.3f} R={R:.3f} F1={F:.3f}")
    return rows


if __name__ == "__main__":
    for thr in (0.55, 0.60, 0.65, 0.70):
        evaluate(thr)
    print("\n--- FN/FP at thr=0.60 (compressed) ---")
    for plat, e, v, s, n in evaluate(0.60):
        if e != v:
            print(f"  {'FP' if v else 'FN'} {plat:9} {s:.2f} {n[:42]}")
