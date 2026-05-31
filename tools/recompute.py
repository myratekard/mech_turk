"""Recompute verification metrics from an existing report.json with label corrections."""
import json
import sys

r = json.load(open("report.json", encoding="utf-8"))
# Files that were mislabeled not_verified but are actually verified:
FIX = {
    "10.06.26 PM (2)", "10.06.26 PM (1)",          # instagram boohooman, raybanmeta
    "10.05.14 PM (4)", "10.05.15 PM (3)",          # tiktok luluandgeorgia x2
    "10.06.52 PM (2)", "10.06.53 PM (10)",         # twitter Imran, Emma ik Umeh
}


def corrected(row):
    for k in FIX:
        if k in row["file"]:
            return True
    return row["expected_verified"]


tp = fp = tn = fn = 0
for row in r["rows"]:
    if row.get("error"):
        continue
    ev, pv = corrected(row), row["pred_verified"]
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
acc = (tp + tn) / (tp + fp + tn + fn)
print("CORRECTED BASELINE (current prompt):")
print(f"  TP={tp} FP={fp} TN={tn} FN={fn}")
print(f"  precision={prec:.3f} recall={rec:.3f} accuracy={acc:.3f}")
print(f"  platform_accuracy={r['metrics']['platform_accuracy']}")
