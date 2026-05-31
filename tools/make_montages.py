"""Stack the top-region crops into labeled montage sheets for fast manual labeling.

Each sheet stacks up to PER_SHEET crops vertically; each crop gets an index banner
like 'instagram #003' drawn above it. Reading a handful of sheets is far cheaper
than reading every screenshot individually.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("_label")
PLATFORMS = ["instagram", "tiktok", "twitter"]
PER_SHEET = 3
BANNER_H = 26
PADDING = 6


def _font():
    try:
        return ImageFont.truetype("arial.ttf", 18)
    except Exception:
        return ImageFont.load_default()


def main():
    font = _font()
    sheet_count = 0
    for plat in PLATFORMS:
        d = OUT / plat
        if not d.exists():
            continue
        crops = sorted([p for p in d.iterdir() if p.suffix.lower() == ".png" and "__" in p.name])
        for start in range(0, len(crops), PER_SHEET):
            batch = crops[start:start + PER_SHEET]
            tiles = []
            for cp in batch:
                idx = cp.name.split("__")[0]
                im = Image.open(cp).convert("RGB")
                w = im.width
                tile = Image.new("RGB", (w, im.height + BANNER_H), (20, 20, 20))
                tile.paste(im, (0, BANNER_H))
                dr = ImageDraw.Draw(tile)
                dr.text((6, 3), f"{plat} #{idx}", fill=(0, 255, 120), font=font)
                tiles.append(tile)
            W = max(t.width for t in tiles)
            H = sum(t.height for t in tiles) + PADDING * (len(tiles) + 1)
            sheet = Image.new("RGB", (W, H), (60, 60, 60))
            y = PADDING
            for t in tiles:
                sheet.paste(t, (0, y))
                y += t.height + PADDING
            out = OUT / f"sheet_{plat}_{start // PER_SHEET:02d}.png"
            sheet.save(out)
            sheet_count += 1
    print(f"wrote {sheet_count} montage sheets to {OUT}")


if __name__ == "__main__":
    main()
