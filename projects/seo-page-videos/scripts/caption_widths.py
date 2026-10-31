"""List every caption in a story that is wider than the builder allows, so they can all be shortened in one pass.

Usage: caption_widths.py <story-name>
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import build_story_video as B

d = json.load(open(Path(__file__).parent / "stories" / f"{sys.argv[1]}.json"))
font = ImageFont.truetype(B.FONT, 96, index=1)
dr = ImageDraw.Draw(Image.new("RGB", (1, 1)))
bad = 0
for b in d["beats"]:
    for k in b["kinetic"]:
        w = dr.textlength(k[0] + " ", font=font)
        if w > B.ART_W - 80:
            bad += 1
            print(f"{b['id']}: {k[0]!r} {int(w)} px (limit {B.ART_W - 80})")
print(bad, "too wide")
