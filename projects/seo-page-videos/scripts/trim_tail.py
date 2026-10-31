"""Trim the trailing silence of a voice take down to <keep> seconds (default 0.25), keeping the original as <take>.pretail.mp3.

Usage: trim_tail.py <take.mp3> [keep_s]
trim_gap.py pads silence onto a take's end to hold its length; once the cuts are final, this takes the pad off so the story's
own pause setting decides the gap before the next line.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


def main(mp3, keep=0.25):
    p = Path(mp3)
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(p), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float))
    a /= a.max()
    hop = 160
    env = a[: len(a) // hop * hop].reshape(-1, hop).mean(1)
    live = np.where(env > 0.02)[0]
    end = (live[-1] + 1) / 100 + keep
    total = len(a) / 16000
    if end >= total - 0.05:
        print("ok", p.name, "no tail to trim")
        return
    pre = p.with_suffix(".pretail.mp3")
    if not pre.exists():
        shutil.copy(p, pre)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pre), "-t", f"{end:.3f}", "-c:a", "libmp3lame", "-q:a", "2", str(p)], check=True)
    print("ok", p.name, "tail trimmed", round(total - end, 2), "s")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) == 3 else 0.25)
