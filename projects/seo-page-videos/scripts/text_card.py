"""A flat still that carries exact words, in the page videos' warm vector style (so names are spelled right, never drawn by a model).

Usage: text_card.py <out.png> <card text> [<card text> ...]   (1 card: one wide card; 2 to 4 cards: a grid; a card may be "Title|small line")
2752x1536, warm ground, cream rounded cards with an orange top bar and dark text. Every line is asserted to fit inside its card.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 2752, 1536
GROUND, CREAM, ORANGE, INK = (23, 17, 12), (241, 230, 214), (255, 107, 44), (23, 17, 12)
FONT = "/System/Library/Fonts/Helvetica.ttc"


def fit(d, text, width, start):
    size = start
    while size > 40 and d.textlength(text, font=ImageFont.truetype(FONT, size, index=1)) > width:
        size -= 4
    return ImageFont.truetype(FONT, size, index=1)


def main(out, cards):
    im = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(im)
    n = len(cards)
    cols = 1 if n == 1 else 2
    rows = (n + cols - 1) // cols
    if n == 3:   # three cards in one row, big
        cols, rows = 3, 1
    if n == 2:   # a two-card row: big, equal type, an orange check or minus for "+" and "-" cards
        cols, rows = 2, 1
    cw, ch = (2000, 780) if n == 1 else ((1220, 860) if n == 2 else ((840, 760) if n == 3 else (900, 360)))
    gap = 60
    x0 = (W - (cols * cw + (cols - 1) * gap)) // 2
    y0 = (H - (rows * ch + (rows - 1) * gap)) // 2
    for i, text in enumerate(cards):
        title, _, small = text.partition("|")
        x, y = x0 + (i % cols) * (cw + gap), y0 + (i // cols) * (ch + gap)
        d.rounded_rectangle((x, y, x + cw, y + ch), 40, fill=CREAM)
        d.rounded_rectangle((x, y, x + cw, y + 40), 20, fill=ORANGE)
        d.rectangle((x, y + 20, x + cw, y + 40), fill=ORANGE)
        mark = title[0] if title[:1] in "+-" else ""
        title = title[1:] if mark else title
        sizes = [fit(d, t.partition("|")[0].lstrip("+-"), cw - 120, 200 if n == 1 else (140 if n == 2 else (110 if n > 3 else 120))).size for t in cards]
        f = ImageFont.truetype(FONT, min(sizes), index=1)   # every card in a set uses the same type size
        assert d.textlength(title, font=f) <= cw - 120, title
        ty = y + ch / 2 + (-30 if small else 20) + (150 if mark else 0)
        if mark:
            cx, cy, r = x + cw / 2, y + ch / 2 - 130, 120
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ORANGE)
            if mark == "+":
                d.line([(cx - 58, cy + 5), (cx - 16, cy + 48), (cx + 62, cy - 45)], fill=CREAM, width=30, joint="curve")
            else:
                d.line([(cx - 58, cy), (cx + 58, cy)], fill=CREAM, width=30)
        d.text((x + cw / 2, ty), title, font=f, fill=INK, anchor="mm")
        if small:
            fs = fit(d, small, cw - 160, 120 if n == 1 else 90)
            d.text((x + cw / 2, ty + 160 if n == 1 else ty + 130), small, font=fs, fill=(176, 60, 14), anchor="mm")
    im.save(out)
    print("ok", out)


if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 6:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
