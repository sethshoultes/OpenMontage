"""Assemble the piece 3 clip (memberintel-marketing#721) from the two real takes: silent, 1920x1080, no subtitles.

Usage: assemble_clip.py            (reads ../renders/terminal-take.mp4 and browser-take.webm, writes ../renders/one-command.mp4)
The terminal take is cut only AFTER the real wait: it runs from the typed command through the real boot to the
"Ready!" line and holds there. Nothing between typing and "Ready!" is cut or sped up.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).resolve().parent.parent / "renders"
HOLD, FADE = 1.6, 0.5


def ready_time(path):
    """Seconds at which the green "Ready!" line first shows in the terminal take."""
    import os, tempfile
    tmp = os.path.join(tempfile.gettempdir(), "ready-probe.png")
    for k in range(0, 120):
        t = k / 2
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-vf", "scale=480:-1", tmp], check=True)
        im = Image.open(tmp).convert("RGB")
        px = im.load()
        if sum(1 for x in range(im.width) for y in range(im.height) if px[x, y][1] > 150 and px[x, y][0] < 120 and px[x, y][2] < 150) > 25:
            return t
    raise SystemExit("no Ready! line in the terminal take")


READY = ready_time(R / "terminal-take.mp4")
B0, B1 = 2.8, 12.6                    # browser take: skip the first blank 2.8 s, keep the site then the dashboard
CREDIT = 2.5
F = lambda s, b=True: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", s, index=1 if b else 0)

im = Image.new("RGB", (1920, 1080), "#0b0d10")
d = ImageDraw.Draw(im)
for text, y, f, fill in (("WordPress Playground", 380, F(130), "#f4f4f5"),
                         ("wordpress.github.io/wordpress-playground", 570, F(66, False), "#a1a7b0")):
    d.text(((1920 - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)
im.save(R / "credit.png")

t_len = READY + HOLD
subprocess.run(["ffmpeg", "-y", "-v", "error",
                "-t", f"{t_len:.2f}", "-i", str(R / "terminal-take.mp4"),
                "-ss", str(B0), "-t", str(B1 - B0), "-i", str(R / "browser-take.webm"),
                "-loop", "1", "-framerate", "30", "-t", str(CREDIT + FADE), "-i", str(R / "credit.png"),
                "-filter_complex",
                f"[0:v]fps=30,scale=1920:1080,format=yuv420p,setpts=PTS-STARTPTS[a];"
                f"[1:v]fps=30,scale=1920:1080,format=yuv420p,setpts=PTS-STARTPTS[b];"
                f"[2:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[c];"
                f"[a][b]xfade=transition=fade:duration={FADE}:offset={t_len - FADE:.2f}[ab];"
                f"[ab][c]xfade=transition=fade:duration={FADE}:offset={t_len + (B1 - B0) - 2 * FADE:.2f}[v]",
                "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(R / "one-command.mp4")], check=True)
print("OK", R / "one-command.mp4")
