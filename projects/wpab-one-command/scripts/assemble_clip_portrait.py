"""Assemble the portrait (1080x1920) piece 3 clip from the two real portrait takes (memberintel-marketing#721).

Reads ../renders/terminal-take-portrait.mp4 (the real run in a 1080x3200 terminal, so nothing scrolls) and
browser-take-portrait.webm; writes ../renders/one-command-portrait.mp4. Silent, no subtitles.
The post quotes two output lines only, so the terminal part shows three bands cropped from the real recording and stacked:
the typed command, the "PHP 8.3  WordPress latest" line and the "Ready!" lines. The other output lines (the site folder,
Extensions, Mount) are cropped out, never painted over; the three bands are real pixels, unscaled and unaltered.
The wait between the typed command and "Ready!" is not cut or sped up.
"""
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).resolve().parent.parent / "renders"
W, H = 1080, 1920
BANDS = [(30, 165), (852, 80), (1745, 230)]   # (y, height) in the 1080x3200 terminal: command, PHP line, Ready lines
GAP = 70
HOLD, FADE, CREDIT = 1.6, 0.5, 2.5
B0, B1 = 2.8, 10.6                            # the browser take: skip the first blank 2.8 s, keep the site then the dashboard
GROUND = (22, 22, 22)


def ready_time(path):
    """First second at which the green 'Ready!' shows in the Ready band."""
    tmp = R / "ready-probe-p.png"
    y, h = BANDS[2]
    for k in range(0, 160):
        t = k / 2
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                        "-vf", f"crop=1080:{h}:0:{y},scale=540:-1", str(tmp)], check=True)
        a = np.asarray(Image.open(tmp).convert("RGB")).astype(int)
        if ((a[..., 1] > 150) & (a[..., 0] < 120) & (a[..., 2] < 150)).sum() > 25:
            return t
    raise SystemExit("no Ready! in the terminal take")


READY = ready_time(R / "terminal-take-portrait.mp4")
t_len = READY + HOLD
# terminal bands stacked on one 1080x1920 frame, same ground as the terminal
gaps = GAP * (len(BANDS) - 1)
total_h = sum(h for _, h in BANDS) + gaps
y0 = (1500 - total_h) // 2
chains, ys, y = [], [], y0
for i, (by, bh) in enumerate(BANDS):
    chains.append(f"[0:v]crop=1080:{bh}:0:{by},setpts=PTS-STARTPTS[b{i}]")
    ys.append(y)
    y += bh + GAP
fc = [f"color=c=0x{GROUND[0]:02x}{GROUND[1]:02x}{GROUND[2]:02x}:s={W}x{H}:r=30:d={t_len:.2f}[bg]"] + chains
last = "bg"
for i, yy in enumerate(ys):
    fc.append(f"[{last}][b{i}]overlay=0:{yy}[o{i}]")
    last = f"o{i}"
fc.append(f"[{last}]format=yuv420p[term]")

# credit card
im = Image.new("RGB", (W, H), (11, 13, 16))
d = ImageDraw.Draw(im)
f = lambda s: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", s, index=1)
for text, yy, fnt, fill in (("WordPress", 700, f(130), "#f4f4f5"), ("Playground", 850, f(130), "#f4f4f5"),
                            ("wordpress.github.io/", 1060, f(60), "#a1a7b0"), ("wordpress-playground", 1140, f(60), "#a1a7b0")):
    d.text((W / 2, yy), text, font=fnt, fill=fill, anchor="mm")
im.save(R / "credit-portrait.png")

fc += [f"[1:v]fps=30,scale={W}:{H},format=yuv420p,setpts=PTS-STARTPTS[br]",
       f"[2:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[cr]",
       f"[term]fps=30[t30]",
       f"[t30][br]xfade=transition=fade:duration={FADE}:offset={t_len - FADE:.2f}[tb]",
       f"[tb][cr]xfade=transition=fade:duration={FADE}:offset={t_len + (B1 - B0) - 2 * FADE:.2f}[v]"]
subprocess.run(["ffmpeg", "-y", "-v", "error",
                "-t", f"{t_len:.2f}", "-i", str(R / "terminal-take-portrait.mp4"),
                "-ss", str(B0), "-t", str(B1 - B0), "-i", str(R / "browser-take-portrait.webm"),
                "-loop", "1", "-framerate", "30", "-t", str(CREDIT + FADE), "-i", str(R / "credit-portrait.png"),
                "-filter_complex", ";".join(fc), "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(R / "one-command-portrait.mp4")], check=True)
print("OK", R / "one-command-portrait.mp4", "ready at", READY)
