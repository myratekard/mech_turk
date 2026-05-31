"""Generate top-region crops of each sample for manual ground-truth labeling.

Crops the top fraction of each profile screenshot (where name/handle/badge live),
resizes to a legible width, and writes them to _label/<platform>/NNN__<name>.png.
Also writes _label/manifest.json mapping crop -> original path.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

SRC = Path("verify/samples")
OUT = Path("_label")
PLATFORMS = ["instagram", "tiktok", "twitter"]
TOP_FRAC = 0.42
WIDTH = 760


def main():
    OUT.mkdir(exist_ok=True)
    manifest = {}
    for plat in PLATFORMS:
        folder = SRC / plat
        if not folder.exists():
            continue
        out_dir = OUT / plat
        out_dir.mkdir(parents=True, exist_ok=True)
        imgs = sorted([p for p in folder.iterdir() if p.suffix.lower() in {".jpeg", ".jpg", ".png"}])
        for i, p in enumerate(imgs):
            im = Image.open(p).convert("RGB")
            w, h = im.size
            crop = im.crop((0, 0, w, int(h * TOP_FRAC)))
            scale = WIDTH / crop.width
            crop = crop.resize((WIDTH, int(crop.height * scale)), Image.LANCZOS)
            name = f"{i:03d}__{p.stem}.png"
            crop.save(out_dir / name)
            manifest[f"{plat}/{name}"] = str(p)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(manifest)} crops to {OUT}")


if __name__ == "__main__":
    main()
