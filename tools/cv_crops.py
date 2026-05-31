"""Crop the detected badge neighborhood for each flagged full-res sample into a montage,
so we can eyeball precision (are they real verified badges?)."""
import glob
from PIL import Image, ImageDraw, ImageFont
from tools.cv_lab import detect, _bgr

fs = sorted(glob.glob("verify/samples/_fullres/*.PNG"))
crops = []
for f in fs:
    try:
        v, s, box = detect(_bgr(f))
    except Exception:
        v, box = False, None
    if not v or not box:
        continue
    im = Image.open(f).convert("RGB")
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    side = max(x2 - x1, y2 - y1)
    half = int(side * 3)  # show badge + surrounding name text
    crop = im.crop((max(0, cx - half), max(0, cy - int(side * 1.2)), cx + half, cy + int(side * 1.2)))
    crop = crop.resize((460, int(crop.height * 460 / crop.width)))
    name = f.replace("\\", "/").split("/")[-1]
    crops.append((name, crop))

# montage: 2 columns
cols = 2
cellw, cellh = 470, 150
rows = (len(crops) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cellw, rows * cellh + 20), (15, 15, 22))
dr = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("arial.ttf", 14)
except Exception:
    font = ImageFont.load_default()
for i, (name, crop) in enumerate(crops):
    r, c = divmod(i, cols)
    x, y = c * cellw + 5, r * cellh + 5
    cc = crop.crop((0, 0, min(crop.width, cellw - 10), min(crop.height, cellh - 24)))
    sheet.paste(cc, (x, y + 18))
    dr.text((x, y), name, fill=(0, 255, 180), font=font)
out = "verify/samples/_fullres/_flagged_review.png"
sheet.save(out)
print(f"{len(crops)} flagged crops -> {out}")
