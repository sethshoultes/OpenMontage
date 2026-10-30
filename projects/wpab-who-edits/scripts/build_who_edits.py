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


def _greedy(d, text, f, width):
    out, line = [], ""
    for w in text.split():
        if d.textlength((line + " " + w).strip(), font=f) > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + [line]


def wrap(text, f, width):
    """Wrap to `width`, then narrow the measure while the row count stays the same, so no line is left with one orphan word."""
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    rows = _greedy(d, text, f, width)
    while len(rows) > 1 and width > 300:
        tighter = _greedy(d, text, f, width - 20)
        if len(tighter) != len(rows):
            break
        width -= 20
        rows = tighter
    return rows


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


def stack(specs, gap=56, lift=0):
    """Lay out [(start_s, text, size, fill, bold, lead, extra)] top to bottom, then centre the whole stack in y 192-1530.
    Returns [(start_s, element)] for scene_text. Every block is built at y=TOP first (the safe-zone check), then shifted."""
    built = []
    for start, text, size, fill, bold, lead, extra in specs:
        built.append((start, block(text, size, TOP, fill=fill, bold=bold, lead=lead, **extra)))
    total = sum(e[2] - e[1] for _, e in built) + gap * (len(built) - 1)
    assert total <= BOTTOM - TOP, f"stack too tall: {total}"
    y = TOP + (BOTTOM - TOP - total) // 2 - lift
    assert y >= TOP, f"lifted above the safe zone: {y}"
    out = []
    for start, (im, y0, y1) in built:
        out.append((start, (im, y, y + (y1 - y0))))
        y += (y1 - y0) + gap
    return out


def T(start, text, size, fill=TEXT, bold=True, lead=1.18, **extra):
    return (start, text, size, fill, bold, lead, extra)


def scene_dots():
    """193 dots, one per site, filling the band; 80% light up."""
    cols, pitch, r = 14, 56, 21
    gx = (W - cols * pitch) // 2 + pitch // 2
    rows = math.ceil(SITES / cols)
    head = block("AI agents built 193 sites without WordPress.", 62, 205, lead=1.15, center=True)
    gy = head[2] + 24
    big = block("80%", 112, gy + rows * pitch + 4, fill=ACCENT, center=True)
    cap = block("of those 193 sites chose how to build without asking who would update the site, or how.", 56, big[2] + 2, lead=1.2, center=True)
    n_on = round(SITES * SHARE)

    def draw(frame, t, dur):
        out = 1 - ease((t - (dur - 0.5)) / 0.5)
        paint(frame, head, ease(t / 0.5) * out)
        fill = int(SITES * ease((t - 0.1) / 0.6))  # the field fills in, then the 80% lights up
        lit = int(n_on * ease((t - 2.6) / 3.0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for i in range(fill):
            cx, cy = gx + (i % cols) * pitch, gy + (i // cols) * pitch + r
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT if i < lit else DIM)
        if out < 1:
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * out)))
        frame.paste(layer, (0, 0), layer)
        paste_big = ease((t - 2.6) / 0.6) * out
        paint(frame, big, paste_big)
        paint(frame, cap, ease((t - 3.4) / 0.6) * out)
    return draw


def build(out):
    s1 = scene_text(stack([T(0.3, "In one benchmark of AI-built sites, 193 were built without WordPress.", 80, lead=1.2, center=True),
                           T(1.2, "Who will edit your site once it's live?", 88, fill=ACCENT, lead=1.15, center=True)], gap=90), 7.0)

    s3a = scene_text(stack([T(0.3, "54%", 190, fill=ACCENT, center=True),
                            T(0.8, "of the sites, asked afterwards: the agents named owners or staff editing without code as the case for WordPress.", 60, lead=1.22, center=True)], gap=40), 6.0)

    s3b = scene_text(stack([T(0.3, "\u201cIf easy self-service updates are your priority, I'd favor WordPress for this bakery site.\u201d", 74, lead=1.2, center=True),
                            T(1.0, "One AI agent, asked afterwards", 58, bold=False, center=True),
                            T(1.8, "As the benchmark puts it, they knew; the question just never came up.", 64, fill=ACCENT, lead=1.18, center=True)], gap=70), 9.0)

    fit = ["You or your team edit it, with no code", "Several people publish", "You run a membership or sell courses", "Your current site is stuck: nobody can change it"]
    items = [T(0.3, "WordPress fits when\u2026", 100), T(0.3, "Advice from this post", 56, bold=False)]
    for i, t in enumerate(fit):
        items.append(T(1.2 + i * 1.3, t, 72, lead=1.15, marker=("check", ACCENT)))
    s4 = scene_text(stack(items, gap=64), 10.0)

    poor = ["It's software with logins and its own rules", "It's documentation your developers keep with their code", "It's one page that rarely changes"]
    items = [T(0.3, "Something simpler fits when\u2026", 100), T(0.3, "Advice from this post", 56, bold=False)]
    for i, t in enumerate(poor):
        items.append(T(1.2 + i * 1.3, t, 72, lead=1.15, marker=("dash", MUTED)))
    s5 = scene_text(stack(items, gap=64), 9.0)

    s6 = scene_text(stack([T(0.3, "So, who will edit your site?", 104, lead=1.12, center=True),
                           T(1.0, ["If it's you or your team,", "WordPress fits."], 74, fill=ACCENT, center=True)], gap=80), 7.0)

    s7 = scene_text(stack([T(0.3, "The question and every number come from WordPress Agent Benchmarks, an open source project started by Andy Peatling.", 60, lead=1.2, center=True, width=W - 2 * 70),
                           T(1.2, "The lists of when WordPress fits are this post's own advice.", 56, bold=False, lead=1.2, center=True, width=W - 2 * 70)], gap=70), 7.5)

    scenes = [(s1, 7.0), (scene_dots(), 11.0), (s3a, 6.0), (s3b, 9.0), (s4, 10.0), (s5, 9.0), (s6, 7.0), (s7, 7.5)]
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
