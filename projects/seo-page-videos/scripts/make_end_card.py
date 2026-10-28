"""The closing card for a page video: the site address and a call to action, hard-edged vector, drawn at 2688x1520.

Usage: make_end_card.py <out.png> [site] [button text]
"""
import sys

from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]
site = sys.argv[2] if len(sys.argv) > 2 else "sethshoultes.com"
label = sys.argv[3] if len(sys.argv) > 3 else "Book a call"
W, H = 2688, 1520
GROUND, CREAM, ORANGE = (23, 17, 12), (241, 230, 214), (255, 107, 44)
f = lambda s: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", s, index=1)
im = Image.new("RGB", (W, H), GROUND)
d = ImageDraw.Draw(im)
d.text((W / 2, 620), site, font=f(230), fill=CREAM, anchor="mm")
bw, bh = 880, 220
x0, y0 = (W - bw) / 2, 820
d.rounded_rectangle((x0 + 18, y0 + 18, x0 + bw + 18, y0 + bh + 18), 110, fill=(70, 38, 20))   # hard offset shadow
d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 110, fill=ORANGE)
d.text((W / 2, y0 + bh / 2), label, font=f(110), fill=GROUND, anchor="mm")
d.rectangle((W / 2 - 160, 450, W / 2 + 160, 466), fill=ORANGE)
im.save(out)
