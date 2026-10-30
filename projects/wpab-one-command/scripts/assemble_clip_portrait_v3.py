#!/usr/bin/env python3
"""Piece 3 portrait v3 (memberintel-marketing#721, herdos#3387): 1080x1920, silent, everything inside y 192-1530.

An opening card, then the real terminal run (one-command-wide60.tape, 60 px type, prompt "$ ") cut into rows on word
boundaries and stacked at 1:1 scale (no text is rescaled), two plain captions, and a closing card. The wait while the run
boots is cut: the take is used from 0 to TYPED_S (the command being typed) and from OUT_A to OUT_B (the finished output).

The layout is centred in the band in both states. While the command types, the panel is just big enough for the command
and the status line, and the stack is centred (layout A). As the status line finishes, the stack eases to layout B
(taller panel, caption above moved up), where the output and the lower caption fit and the whole stack is centred
again. Nothing overlaps while it moves. Text margins are 74 px.

  assemble_clip_portrait_v3.py <terminal-take-wide60.mp4> <out.mp4>
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 25
TOP, BOT = 192, 1530
BG = (13, 13, 13)                       # the card and canvas colour; the terminal panel is the take's own (23, 23, 23), so a blank crop is invisible on it
TEXT = (244, 244, 245)
FONT = "/System/Library/Fonts/Helvetica.ttc"
OPEN = "Want to try WordPress without risking your site?"
CAP1 = "One command makes a practice copy of WordPress."
CAP2 = "Open that address in your browser to see your practice site."
STATUS = "Starting your practice copy..."
CLOSE = "A practice copy on your own computer. Nothing reaches your members."
OPEN_S, CLOSE_S, FADE = 4.0, 4.5, 0.4
TYPED_S = 6.0                           # the command is typed by 3.9 s in the take; the rest to here is the real boot wait, shown with a status line
STATUS_FROM = 4.2                       # "Starting your practice copy..." from here to TYPED_S
OUT_A, OUT_B = 16.6, 21.2               # the take's finished output (Ready! ...), held 4.6 s
SHIFT_D = 0.8                           # the stack eases from layout A to layout B over the last SHIFT_D seconds of the status line
TAKE_S = TYPED_S + (OUT_B - OUT_A)

# Layout A (typing) and layout B (output), each centred in the band. y values are frame y.
PANEL_A = (734, 440)                    # y, h
PANEL_B = (427, 780)
PX, PW = 40, 1000                       # panel x and width
CAP1_Y = (626, 319)                     # centre of the caption above the panel: A, B
CAP2_Y = 1364                           # the lower caption sits in its reserved slot from the first frame; it fades in with the output
STATUS_Y = (1100, 900)                  # centre of the status line: A, B (it is gone before B matters)
# rows cut from the 2560x1500 take: (take x, take y, w, h, frame y in A, frame y in B)
TYPED = [
    (35, 46, 210, 64, 784, 497),       # "$ npx"
    (255, 46, 950, 64, 864, 597),      # "@wp-playground/cli@latest"
    (1237, 46, 200, 64, 944, 697),     # "start"
]
OUTPUT = [                              # (take x, take y, w, h, frame y); shown from TYPED_S, in layout B
    (35, 1246, 230, 76, 857),          # "Ready!"
    (292, 1246, 880, 76, 957),         # "WordPress is running on"
    (1197, 1246, 800, 76, 1057),       # "http://127.0.0.1:9400"
]
OX = 64                                  # crops start 10 px before the text, so the text starts at 74


def card(text, path, size=68, y_center=None, band=(TOP, BOT)):
    f = ImageFont.truetype(FONT, size, index=1)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0) if y_center else BG + (255,))
    d = ImageDraw.Draw(im)

    def wrap_at(width):
        out, line = [], ""
        for w in text.split():
            if d.textlength((line + " " + w).strip(), font=f) > width:
                out.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        return out + [line]
    width = W - 2 * 74
    rows = wrap_at(width)
    while True:                       # balance the lines: narrow the measure while the row count stays the same (no one-word last line)
        tighter = wrap_at(width - 20)
        if len(tighter) != len(rows) or width < 300:
            break
        width -= 20
        rows = tighter
    lead = int(size * 1.3)
    y = (y_center - len(rows) * lead // 2) if y_center else (band[0] + band[1]) // 2 - len(rows) * lead // 2
    assert band[0] <= y and y + len(rows) * lead <= band[1], text
    for r in rows:
        d.text(((W - d.textlength(r, font=f)) / 2, y), r, font=f, fill=TEXT)
        y += lead
    im.save(path)


def ease(a, b, t0, d):
    """An ffmpeg expression: a at t0, b at t0+d, smoothstep between."""
    p = f"clip((t-{t0})/{d},0,1)"
    return f"({a}+({b}-{a})*(3*pow({p},2)-2*pow({p},3)))"


def main(take, out):
    t0 = TYPED_S - SHIFT_D
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        card(OPEN, td / "open.png", size=80)
        card(CLOSE, td / "close.png")
        card(CAP1, td / "cap1.png", size=60, y_center=CAP1_Y[0])
        card(CAP2, td / "cap2.png", size=60, y_center=CAP2_Y)
        card(STATUS, td / "status.png", size=60, y_center=STATUS_Y[0])
        # every state of every element stays inside the band
        assert TOP <= min(PANEL_A[0], PANEL_B[0]) and max(sum(PANEL_A), sum(PANEL_B)) <= BOT
        n = len(TYPED) + len(OUTPUT)
        chain = (f"[0:v]fps={FPS},split=2[ta][tb];[ta]trim=0:{TYPED_S},setpts=PTS-STARTPTS[a];"
                 f"[tb]trim={OUT_A}:{OUT_B},setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1[t];"
                 f"[t]split={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
                 f"color=c=#0d0d0d:s={W}x{H}:r={FPS}:d={TAKE_S}[bg];")
        crops = list(TYPED) + [(x, y, w, h, fy, fy) for (x, y, w, h, fy) in OUTPUT]
        for i, (x, y, w, h, ya, yb) in enumerate(crops):
            assert OX + w <= W - 60 and TOP <= min(ya, yb) and max(ya, yb) + h <= BOT, crops[i]
            chain += f"[s{i}]crop={w}:{h}:{x}:{y}[r{i}];"
        # the panel: an outline layer and a fill layer, both scaled per frame so the panel grows downward as the stack eases
        ph = ease(PANEL_A[1], PANEL_B[1], t0, SHIFT_D)
        py = ease(PANEL_A[0], PANEL_B[0], t0, SHIFT_D)
        chain += (f"color=c=#2c2c2c:s={PW}x{PANEL_B[1]}:r={FPS}:d={TAKE_S},scale=w={PW}:h='2*trunc({ph}/2)':eval=frame[po];"
                  f"color=c=#171717:s={PW - 6}x{PANEL_B[1]}:r={FPS}:d={TAKE_S},scale=w={PW - 6}:h='2*trunc(({ph}-6)/2)':eval=frame[pf];"
                  f"[bg][po]overlay=x={PX}:y='{py}'[b1];[b1][pf]overlay=x={PX + 3}:y='{py}+3'[pn];")
        last = "pn"
        for i, (x, y, w, h, ya, yb) in enumerate(crops):
            if i < len(TYPED):
                chain += f"[{last}][r{i}]overlay={OX}:'{ease(ya, yb, t0, SHIFT_D)}'[o{i}];"
            else:
                chain += f"[{last}][r{i}]overlay={OX}:{ya}:enable='gte(t,{TYPED_S})'[o{i}];"
            last = f"o{i}"
        # captions: the one above moves with the panel; the one below fades in on its reserved slot; the status line moves with the panel
        sy = ease(0, STATUS_Y[1] - STATUS_Y[0], t0, SHIFT_D)
        cy = ease(0, CAP1_Y[1] - CAP1_Y[0], t0, SHIFT_D)
        chain += (f"[{last}][1:v]overlay=0:'{cy}'[c1];"
                  f"[2:v]format=rgba,fade=t=in:st={TYPED_S}:d=0.5:alpha=1[cp2];[c1][cp2]overlay=0:0[c2];"
                  f"[c2][3:v]overlay=0:'{sy}':enable='gte(t,{STATUS_FROM})*lt(t,{TYPED_S})',format=yuv420p[v]")
        term = td / "term.mp4"
        subprocess.run(["nice", "ffmpeg", "-v", "error", "-y", "-threads", "2", "-i", str(take), "-loop", "1", "-i", str(td / "cap1.png"),
                        "-loop", "1", "-i", str(td / "cap2.png"), "-loop", "1", "-i", str(td / "status.png"), "-filter_complex", chain,
                        "-map", "[v]", "-t", f"{TAKE_S:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "medium", str(term)], check=True)
        parts = []
        for name, png, dur in (("open", td / "open.png", OPEN_S), ("close", td / "close.png", CLOSE_S)):
            p = td / f"{name}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", str(png),
                            "-vf", f"fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE}:d={FADE},format=yuv420p",
                            "-c:v", "libx264", "-crf", "16", str(p)], check=True)
            parts.append(p)
        lst = td / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in (parts[0], term, parts[1])))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-an", "-c:v", "libx264", "-crf", "16",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    print("OK", out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
