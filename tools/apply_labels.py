"""Apply manual ground-truth labels: move each sample into
verify/samples/<platform>/{verified,not_verified}/ based on the index sets below.

Indices are the NNN prefixes from the _label crops (sorted order per platform).
Run once after labeling; idempotent-ish (skips files already moved).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

OUT = Path("_label")
SAMPLES = Path("verify/samples")

VERIFIED = {
    "instagram": {4, 7, 8, 16, 17, 18, 19, 21},
    "tiktok": {1},
    "twitter": {0, 1, 3, 4, 5, 6, 7, 12, 13, 14, 15, 16, 17, 18, 19, 20},
}


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    moved = 0
    for crop_key, orig in manifest.items():
        plat, name = crop_key.split("/", 1)
        idx = int(name.split("__")[0])
        label = "verified" if idx in VERIFIED.get(plat, set()) else "not_verified"
        src = Path(orig)
        if not src.exists():
            print(f"skip (missing): {src}")
            continue
        dest_dir = SAMPLES / plat / label
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.move(str(src), str(dest))
        moved += 1
    print(f"moved {moved} files into verified/not_verified subfolders")
    # Report counts
    for plat in VERIFIED:
        for label in ("verified", "not_verified"):
            d = SAMPLES / plat / label
            n = len(list(d.glob("*"))) if d.exists() else 0
            print(f"  {plat}/{label}: {n}")


if __name__ == "__main__":
    main()
