import sys, glob, os
from PIL import Image, ImageDraw
d = sys.argv[1]; cols = int(sys.argv[2]) if len(sys.argv) > 2 else 4
fs = sorted(glob.glob(os.path.join(d, '[0-9][0-9]-*.png')))
ims = [Image.open(f) for f in fs]
w = 480 if ims[0].width > 600 else 200
th = [im.resize((w, int(im.height * w / im.width))) for im in ims]
h = max(t.height for t in th) + 18
rows = (len(th) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (w + 8) + 8, rows * (h + 8) + 8), (40, 40, 40))
dr = ImageDraw.Draw(sheet)
for i, (t, f) in enumerate(zip(th, fs)):
    x = 8 + (i % cols) * (w + 8); y = 8 + (i // cols) * (h + 8)
    sheet.paste(t, (x, y)); dr.text((x + 2, y + t.height + 3), os.path.basename(f)[:-4], fill=(230, 230, 230))
sheet.save(os.path.join(d, 'sheet.png')); print('sheet', sheet.size, len(fs))
