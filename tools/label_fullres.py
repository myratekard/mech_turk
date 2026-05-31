"""Label the full-res samples with the LLM (our trusted oracle) -> _labels.json,
so we can iterate the CV detector against real ground truth."""
import glob
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.vision_llm import analyze_screenshot

fs = sorted(glob.glob("verify/samples/_fullres/*.PNG"))


def one(f):
    try:
        va = analyze_screenshot(open(f, "rb").read(), mime="image/png")
        return f, {"platform": va.platform, "verified": bool(va.is_verified),
                   "handle": getattr(va.profile, "handle", None)}
    except Exception as e:
        return f, {"error": str(e)}


labels = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(one, f): f for f in fs}
    for i, fut in enumerate(as_completed(futs), 1):
        f, r = fut.result()
        labels[f.replace("\\", "/").split("/")[-1]] = r
        print(f"[{i}/{len(fs)}] {f.split(chr(92))[-1]:20} -> {r.get('platform')}/{r.get('verified')}")

out = "verify/samples/_fullres/_labels.json"
json.dump(labels, open(out, "w"), indent=2)
v = sum(1 for r in labels.values() if r.get("verified"))
print(f"\nlabeled {len(labels)}: verified={v} not={len(labels)-v} -> {out}")
