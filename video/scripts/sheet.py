"""Contact sheet of the rendered stills: python scripts/sheet.py (writes out/stills/sheet.png)."""
import glob, os
from PIL import Image, ImageDraw

here = os.path.join(os.path.dirname(__file__), "..", "out", "stills")
files = sorted(f for f in glob.glob(os.path.join(here, "element-*.png")))
W, H, cols, pad = 640, 360, 3, 16
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (W + pad) + pad, rows * (H + pad + 28) + pad), (14, 15, 16))
d = ImageDraw.Draw(sheet)
for k, f in enumerate(files):
    im = Image.open(f).convert("RGB").resize((W, H), Image.LANCZOS)
    x, y = pad + (k % cols) * (W + pad), pad + (k // cols) * (H + pad + 28)
    sheet.paste(im, (x, y + 28))
    fr = int(os.path.basename(f).split("-")[1].split(".")[0])
    d.text((x, y + 6), f"frame {fr}  ({fr / 30:.2f} s)", fill=(157, 163, 168))
sheet.save(os.path.join(here, "sheet.png"))
print(len(files), "stills ->", os.path.join(here, "sheet.png"))
