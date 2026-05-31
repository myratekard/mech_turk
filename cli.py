"""mech_turk CLI.

Subcommands:
  analyze   Run the pipeline on a single screenshot and print the AnalysisResult.
  eval      Batch-run the pipeline over a labeled sample tree and report accuracy.

Labeled tree layout (ground truth):
  <dir>/<platform>/<label>/*.jpeg      e.g. verify/samples/instagram/verified/x.jpeg
  <dir>/<platform>/*.jpeg              platform-only GT (no verification label)

Platform folder names: instagram, tiktok, twitter|x. Label folder names:
verified | not_verified (anything else => verification GT unknown).
"""
from __future__ import annotations

import argparse
import json
import sys

# Force UTF-8 stdout so emoji/unicode in extracted profiles don't crash on Windows cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from app.schemas.models import AnalysisResult
from app.services.pipeline import analyze as run_pipeline

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tiff"}
PLATFORM_ALIASES = {"twitter": "x", "x": "x", "instagram": "instagram", "tiktok": "tiktok"}
MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
}


def _gt_from_path(path: Path, root: Path) -> tuple[Optional[str], Optional[bool]]:
    """Infer (expected_platform, expected_verified) from folder names under root."""
    parts = [p.lower() for p in path.relative_to(root).parts]
    platform = None
    verified = None
    for part in parts:
        if part in PLATFORM_ALIASES:
            platform = PLATFORM_ALIASES[part]
        if part in ("verified", "verifed"):
            verified = True
        elif part in ("not_verified", "notverified", "unverified", "not-verified"):
            verified = False
    return platform, verified


def _iter_images(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            yield p


def cmd_analyze(args):
    data = Path(args.image).read_bytes()
    mime = MIME_BY_EXT.get(Path(args.image).suffix.lower(), "image/jpeg")
    result = run_pipeline(data, mime=mime, persist=not args.no_persist)
    print(result.model_dump_json(indent=2))


def _run_one(path: Path, root: Path):
    mime = MIME_BY_EXT.get(path.suffix.lower(), "image/jpeg")
    exp_platform, exp_verified = _gt_from_path(path, root)
    try:
        res: AnalysisResult = run_pipeline(path.read_bytes(), mime=mime, persist=False)
        return {
            "file": str(path.relative_to(root)),
            "expected_platform": exp_platform,
            "expected_verified": exp_verified,
            "pred_platform": res.platform,
            "pred_verified": res.verification.verified,
            "confidence": res.verification.confidence,
            "needs_review": res.verification.needs_review,
            "cv_matched": res.verification.cv_signal.matched,
            "cv_score": res.verification.cv_signal.score,
            "llm_verified": res.verification.llm_signal.is_verified,
            "llm_conf": res.verification.llm_signal.confidence,
            "error": None,
        }
    except Exception as e:
        return {
            "file": str(path.relative_to(root)),
            "expected_platform": exp_platform,
            "expected_verified": exp_verified,
            "error": str(e),
        }


def cmd_eval(args):
    root = Path(args.dir)
    if not root.exists():
        print(f"dir not found: {root}", file=sys.stderr)
        sys.exit(1)

    images = list(_iter_images(root))
    if args.limit:
        images = images[: args.limit]
    print(f"Evaluating {len(images)} images from {root} with {args.workers} workers...")

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_run_one, p, root): p for p in images}
        for i, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            rows.append(row)
            tag = "ERR" if row.get("error") else (
                f"{row['pred_platform']:<9} ver={int(bool(row['pred_verified']))} "
                f"(exp {row['expected_platform']}/{row['expected_verified']})"
            )
            print(f"  [{i}/{len(images)}] {row['file']}  ->  {tag}")

    metrics = _compute_metrics(rows)
    report = {"metrics": metrics, "rows": rows}
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_summary(metrics, args.report)


def _compute_metrics(rows):
    ok_rows = [r for r in rows if not r.get("error")]
    errors = [r for r in rows if r.get("error")]

    # Platform accuracy (only where GT platform known)
    plat_gt = [r for r in ok_rows if r["expected_platform"]]
    plat_correct = sum(1 for r in plat_gt if r["pred_platform"] == r["expected_platform"])
    platform_acc = (plat_correct / len(plat_gt)) if plat_gt else None

    # Verification confusion (only where GT verified known)
    ver_gt = [r for r in ok_rows if r["expected_verified"] is not None]
    tp = sum(1 for r in ver_gt if r["expected_verified"] and r["pred_verified"])
    fn = sum(1 for r in ver_gt if r["expected_verified"] and not r["pred_verified"])
    tn = sum(1 for r in ver_gt if not r["expected_verified"] and not r["pred_verified"])
    fp = sum(1 for r in ver_gt if not r["expected_verified"] and r["pred_verified"])

    def _safe(n, d):
        return round(n / d, 4) if d else None

    precision = _safe(tp, tp + fp)
    recall = _safe(tp, tp + fn)
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if precision and recall
        else None
    )
    accuracy = _safe(tp + tn, len(ver_gt))

    # Per-platform breakdown
    per_platform = {}
    for plat in ("instagram", "x", "tiktok"):
        pr = [r for r in plat_gt if r["expected_platform"] == plat]
        pc = sum(1 for r in pr if r["pred_platform"] == plat)
        vr = [r for r in pr if r["expected_verified"] is not None]
        vc = sum(1 for r in vr if r["pred_verified"] == r["expected_verified"])
        per_platform[plat] = {
            "n": len(pr),
            "platform_acc": _safe(pc, len(pr)),
            "verification_acc": _safe(vc, len(vr)),
        }

    return {
        "n_total": len(rows),
        "n_ok": len(ok_rows),
        "n_errors": len(errors),
        "platform_accuracy": platform_acc,
        "verification": {
            "n": len(ver_gt),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "accuracy": accuracy,
        },
        "needs_review_count": sum(1 for r in ok_rows if r.get("needs_review")),
        "per_platform": per_platform,
    }


def _print_summary(m, report_path):
    print("\n================ EVAL SUMMARY ================")
    print(f"images: {m['n_total']}  ok: {m['n_ok']}  errors: {m['n_errors']}")
    print(f"platform accuracy: {m['platform_accuracy']}")
    v = m["verification"]
    print(
        f"verification (n={v['n']}): precision={v['precision']} recall={v['recall']} "
        f"f1={v['f1']} acc={v['accuracy']}"
    )
    print(f"  confusion  TP={v['tp']} FP={v['fp']} TN={v['tn']} FN={v['fn']}")
    print(f"needs_review: {m['needs_review_count']}")
    print("per-platform:")
    for plat, d in m["per_platform"].items():
        print(
            f"  {plat:<9} n={d['n']:<3} platform_acc={d['platform_acc']} "
            f"verification_acc={d['verification_acc']}"
        )
    print(f"\nfull report -> {report_path}")
    print("=============================================")


def main():
    ap = argparse.ArgumentParser(prog="mech_turk")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="Analyze a single screenshot")
    a.add_argument("image")
    a.add_argument("--no-persist", action="store_true", help="Do not write artifacts")
    a.set_defaults(func=cmd_analyze)

    e = sub.add_parser("eval", help="Batch eval over a labeled sample tree")
    e.add_argument("--dir", default="verify/samples")
    e.add_argument("--report", default="report.json")
    e.add_argument("--workers", type=int, default=4)
    e.add_argument("--limit", type=int, default=0)
    e.set_defaults(func=cmd_eval)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
