"""Compare LLM-only vs CV-only vs fused verification accuracy from a report file."""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "report_v2.json"
r = json.load(open(path, encoding="utf-8"))


def metrics(rows, predkey):
    tp = fp = tn = fn = 0
    for row in rows:
        if row.get("error") or row.get("expected_verified") is None:
            continue
        ev, pv = row["expected_verified"], row[predkey]
        if ev and pv:
            tp += 1
        elif ev and not pv:
            fn += 1
        elif (not ev) and pv:
            fp += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    acc = (tp + tn) / max(1, tp + fp + tn + fn)
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    return tp, fp, tn, fn, prec, rec, f1, acc


rows = r["rows"]
for label, key in [("FUSED", "pred_verified"), ("LLM-only", "llm_verified"), ("CV-only", "cv_matched")]:
    tp, fp, tn, fn, prec, rec, f1, acc = metrics(rows, key)
    print(f"{label:9} TP={tp:2} FP={fp:2} TN={tn:2} FN={fn:2}  "
          f"P={prec:.3f} R={rec:.3f} F1={f1:.3f} Acc={acc:.3f}")
