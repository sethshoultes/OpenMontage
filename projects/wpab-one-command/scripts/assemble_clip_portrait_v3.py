#!/usr/bin/env python3
"""Piece 3 portrait v3 (memberintel-marketing#721, herdos#3387): 1080x1920, silent, everything inside y 192-1530.

An opening card, then the real terminal run (one-command-wide60.tape, 60 px type, prompt "$ ") cut into rows on word
boundaries and stacked at 1:1 scale (no text is rescaled), two plain captions, and a closing card. The wait while the run
boots is cut: the take is used from 0 to TYPED_S (the command being typed) and from OUT_A to OUT_B (the finished output),
and the output rows appear when the cut lands there. Text margins are 74 px.

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
TAKE_S = TYPED_S + (OUT_B - OUT_A)

# (take x, take y, w, h, frame y, shown from take-timeline second or None, extra filter). Text starts at x=74 in the frame.
ROWS = [
    (35, 46, 210, 64, 497, None, None),        # "$ npx"
    (255, 46, 950, 64, 597, None, None),       # "@wp-playground/cli@latest"
    (1237, 46, 200, 64, 697, None, None),      # "start"
    (35, 1246, 230, 76, 857, TYPED_S, None),   # "Ready!"
    (292, 1246, 880, 76, 957, TYPED_S, None),  # "WordPress is running on"
    (1197, 1246, 800, 76, 1057, TYPED_S, None),  # "http://127.0.0.1:9400"
]
PANEL = (40, 427, 1000, 780)             # x, y, w, h: a thin terminal panel behind the block, so the left-aligned text looks deliberate
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


def main(take, out):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        card(OPEN, td / "open.png", size=80)
        card(CLOSE, td / "close.png")
        card(CAP1, td / "cap1.png", size=60, y_center=319)      # y 340-480
        card(CAP2, td / "cap2.png", size=60, y_center=1364)
        card(STATUS, td / "status.png", size=60, y_center=900)     # y 1135-1345
        n = len(ROWS)
        chain = (f"[0:v]fps={FPS},split=2[ta][tb];[ta]trim=0:{TYPED_S},setpts=PTS-STARTPTS[a];"
                 f"[tb]trim={OUT_A}:{OUT_B},setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1[t];"
                 f"[t]split={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
                 f"color=c=#0d0d0d:s={W}x{H}:r={FPS}:d={TAKE_S}[bg];")
        for i, (x, y, w, h, fy, _, extra) in enumerate(ROWS):
            assert TOP <= fy and fy + h <= BOT and OX + w <= W - 60, ROWS[i]
            chain += f"[s{i}]crop={w}:{h}:{x}:{y}" + (f",{extra}" if extra else "") + f"[r{i}];"
        px, py, pw, ph = PANEL
        assert TOP <= py and py + ph <= BOT
        chain += f"[bg]drawbox=x={px}:y={py}:w={pw}:h={ph}:color=0x171717:t=fill,drawbox=x={px}:y={py}:w={pw}:h={ph}:color=0x2c2c2c:t=3[pn];"
        last = "pn"
        for i, (x, y, w, h, fy, start, _) in enumerate(ROWS):
            en = f":enable='gte(t,{start})'" if start is not None else ""
            chain += f"[{last}][r{i}]overlay={OX}:{fy}{en}[o{i}];"
            last = f"o{i}"
        chain += (f"[{last}][1:v]overlay=0:0[c1];[c1][2:v]overlay=0:0:enable='gte(t,{TYPED_S})'[c2];"
                  f"[c2][3:v]overlay=0:0:enable='between(t,{STATUS_FROM},{TYPED_S})',format=yuv420p[v]")
        chain = chain.replace("[c1][2:v]overlay=0:0:enable='gte(t,%s)'[c2]" % TYPED_S, "[2:v]format=rgba,fade=t=in:st=%s:d=0.5:alpha=1[cp2];[c1][cp2]overlay=0:0[c2]" % TYPED_S)
        term = td / "term.mp4"
        subprocess.run(["nice", "ffmpeg", "-v", "error", "-y", "-threads", "2", "-i", str(take), "-loop", "1", "-i", str(td / "cap1.png"),
                        "-loop", "1", "-i", str(td / "cap2.png"), "-loop", "1", "-i", str(td / "status.png"), "-filter_complex", chain, "-map", "[v]", "-t", f"{TAKE_S:.3f}",
                        "-c:v", "libx264", "-crf", "16", "-preset", "medium", str(term)], check=True)
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
