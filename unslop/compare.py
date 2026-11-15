# Scratch: side-by-side before/after contact images for the unslop report.
from pathlib import Path
from PIL import Image, ImageDraw

S = Path(__file__).parent / "shots"


def pair(rows, out, crop_h=1400, w=720):
    """rows: list of file stems; each row shows before | after, cropped to the top crop_h px, scaled to width w."""
    tiles = []
    for stem in rows:
        row = []
        for side in ("before", "after"):
            im = Image.open(S / side / f"{stem}.png").convert("RGB")
            im = im.crop((0, 0, im.width, min(crop_h, im.height)))
            im = im.resize((w, round(im.height * w / im.width)))
            row.append(im)
        tiles.append(row)
    H = sum(max(a.height, b.height) for a, b in tiles) + 40
    sheet = Image.new("RGB", (w * 2 + 24, H), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    d.text((8, 12), "before", fill=(230, 230, 230))
    d.text((w + 32, 12), "after", fill=(230, 230, 230))
    y = 40
    for a, b in tiles:
        sheet.paste(a, (0, y))
        sheet.paste(b, (w + 24, y))
        y += max(a.height, b.height)
    sheet.save(S / out)


pair(["bounds-d-light", "bounds-d-dark"], "compare-bounds.png")
pair(["bounds-m-light"], "compare-bounds-mobile.png", crop_h=2400, w=390)
pair(["home-0-d-light", "home-1-d-light", "home-4_5-d-dark", "home-8-d-light"], "compare-home.png", crop_h=900)
