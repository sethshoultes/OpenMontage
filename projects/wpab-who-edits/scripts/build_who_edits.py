#!/usr/bin/env python3
"""Piece 4 of the myth-vs-data series (memberintel-marketing#720, post #8803 / memberintel#8829):
"Does WordPress Fit Your Site? Start With Who Will Edit It". Silent, 1080x1920, animated type and a dot field,
everything between y=192 and y=1530 (the top 10% and the player's control bar stay empty). Every figure and the
quote come from the post, which reads them from the WordPress Agent Benchmarks data file (Andy Peatling's project).

  build_who_edits.py <out.mp4>
"""
import math
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 25
TOP, BOTTOM = 192, 1530
BG, TEXT, MUTED, ACCENT, DIM = "#0b0d10", "#f4f4f5", "#a1a7b0", "#ff6b2c", "#2a2f37"
FONT = "/System/Library/Fonts/Helvetica.ttc"
MARGIN = 90
SITES, SHARE = 193, 0.80  # 193 sites built without WordPress, 80% chosen without asking who would edit
ease = lambda x: 0.5 - 0.5 * math.cos(math.pi * min(1, max(0, x)))


def font(size, bold=True):
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def wrap(text, f, width):
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    out, line = [], ""
    for w in text.split():
        if d.textlength((line + " " + w).strip(), font=f) > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + [line]


def block(lines, size, y, fill=TEXT, bold=True, lead=1.18, x=MARGIN, width=W - 2 * MARGIN, center=False, marker=None):
    """One element: wrapped text rendered once onto a transparent layer. Returns (layer, y) after a safe-zone check."""
    f = font(size, bold)
    rows = [r for t in ([lines] if isinstance(lines, str) else lines) for r in wrap(t, f, width - (size if marker else 0))]
    h = int(len(rows) * size * lead) + 8
    assert TOP <= y and y + h <= BOTTOM, f"outside the safe zone: {rows[0]!r} y={y}..{y + h}"
    im = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, r in enumerate(rows):
        tx = x + (size if marker else 0)
        if center:
            tx = (W - d.textlength(r, font=f)) / 2
        d.text((tx, i * size * lead), r, font=f, fill=fill)
    if marker:  # drawn, not typed: Helvetica has no check mark
        kind, col = marker
        u = size * 0.62
        if kind == "check":
            d.line([(x + 4, 0.62 * size), (x + 0.28 * u + 4, 0.62 * size + 0.3 * u), (x + 0.78 * u, 0.62 * size - 0.4 * u)], fill=col, width=9, joint="curve")
        else:
            d.line([(x + 4, 0.55 * size), (x + 0.8 * u, 0.55 * size)], fill=col, width=9)
    return im, y, y + h


def paint(frame, el, alpha):
    if alpha <= 0:
        return
    im, y, _ = el
    if alpha < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    frame.paste(im, (0, y), im)


def scene_text(items, hold):
    """items: [(start_s, element)] fading in over 0.5 s; the whole scene fades out over its last 0.5 s."""
    def draw(frame, t, dur):
        out = 1 - ease((t - (dur - 0.5)) / 0.5)
        for t0, el in items:
            paint(frame, el, ease((t - t0) / 0.5) * out)
    return draw


def scene_dots():
    cols, pitch, r = 14, 54, 18
    gx = (W - cols * pitch) // 2 + pitch // 2
    gy = 400
    rows = math.ceil(SITES / cols)
    assert gy + rows * pitch <= 1180
    head = block(f"AI agents built {SITES} sites without WordPress.", 62, 215, lead=1.15)
    big = block("80%", 150, 1190, fill=ACCENT)
    cap = block("chose how to build without asking who would edit it.", 58, 1350, lead=1.3)
    n_on = round(SITES * SHARE)

    def draw(frame, t, dur):
        out = 1 - ease((t - (dur - 0.5)) / 0.5)
        paint(frame, head, ease(t / 0.5) * out)
        grow = ease((t - 1.0) / 1.4)
        fill = int(SITES * grow)  # the field fills in, then the 80% lights up
        lit = int(n_on * ease((t - 3.6) / 3.0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for i in range(fill):
            cx, cy = gx + (i % cols) * pitch, gy + (i // cols) * pitch + r
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT if i < lit else DIM)
        if out < 1:
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * out)))
        frame.paste(layer, (0, 0), layer)
        paint(frame, big, ease((t - 3.6) / 0.6) * out)
        paint(frame, cap, ease((t - 4.4) / 0.6) * out)
    return draw


def build(out):
    q1 = block("ONE QUESTION FIRST", 56, 520, fill=TEXT)
    q2 = block("Who will edit this site once it's live?", 118, 640, lead=1.12)
    s1 = scene_text([(0.3, q1), (0.9, q2)], 6.0)

    asked = block("Asked afterwards, 54% named owners editing without code as the case for WordPress.", 56, 250, lead=1.2)
    quote = block("“If easy self-service updates are your priority, I'd favor WordPress for this bakery site.”", 72, 590, lead=1.2)
    who = block("An AI agent, asked afterwards", 54, 1010, fill=TEXT, bold=False)
    knew = block("They knew. The question never came up.", 70, 1170, fill=ACCENT, lead=1.18)
    s3 = scene_text([(0.3, asked), (2.6, quote), (5.0, who), (6.2, knew)], 10.0)

    h4 = block("WordPress fits when…", 92, 260)
    fit = ["You or your team edit it, with no code", "Several people publish", "You run a membership or sell courses", "A site exists that nobody can change"]
    y, items = h4[2] + 90, [(0.3, h4)]
    for i, t in enumerate(fit):
        el = block(t, 66, y, marker=("check", ACCENT), lead=1.15)
        items.append((1.2 + i * 1.5, el))
        y = el[2] + 70
    s4 = scene_text(items, 9.0)

    h5 = block("A lighter tool fits when…", 92, 260)
    poor = ["It's an app with logins and its own rules", "The docs live next to the code", "It's one page that rarely changes"]
    y, items = h5[2] + 90, [(0.3, h5)]
    for i, t in enumerate(poor):
        el = block(t, 66, y, marker=("dash", MUTED), lead=1.15)
        items.append((1.2 + i * 1.5, el))
        y = el[2] + 70
    s5 = scene_text(items, 7.0)

    a = block("So, who will edit your site?", 110, 520, lead=1.12)
    b = block("If it's you, WordPress fits.", 78, 1000, fill=ACCENT)
    s6 = scene_text([(0.3, a), (2.0, b)], 5.5)

    c1 = block("The question and every number come from WordPress Agent Benchmarks, an open source project started by Andy Peatling.", 58, 560, lead=1.2)
    s7 = scene_text([(0.3, c1)], 4.0)

    scenes = [(s1, 6.0), (scene_dots(), 9.0), (s3, 10.0), (s4, 9.0), (s5, 7.0), (s6, 5.5), (s7, 4.0)]
    ff = subprocess.Popen(["nice", "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                          stdin=subprocess.PIPE)
    total = 0.0
    for draw, dur in scenes:
        for k in range(int(dur * FPS)):
            frame = Image.new("RGBA", (W, H), BG)
            draw(frame, k / FPS, dur)
            ff.stdin.write(frame.convert("RGB").tobytes())
        total += dur
    ff.stdin.close()
    ff.wait()
    print("OK", total, "s", out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    build(sys.argv[1])
