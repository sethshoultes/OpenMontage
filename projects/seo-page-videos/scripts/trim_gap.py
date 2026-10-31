"""Cut a dead pause out of a voice take and pad the same length of silence onto its end, so the line keeps its duration (nothing
after it moves) while the words after the cut come earlier.

Usage: trim_gap.py <take.mp3> <cut_from_s> <cut_to_s>      (times inside the take)
The original is kept as <take>.orig.mp3 beside it. Run whisper_words.py on the vo dir afterwards.
"""
import shutil
import subprocess
import sys
from pathlib import Path


def main(mp3, a, b):
    p = Path(mp3)
    orig = p.with_suffix(".orig.mp3")
    if not orig.exists():
        shutil.copy(p, orig)
    gap = b - a
    src = p.with_suffix(".cur.mp3")   # cut from the current file, so several cuts in one take accumulate (later ones first)
    shutil.copy(p, src)
    flt = (f"[0:a]atrim=0:{a},asetpts=PTS-STARTPTS[x];[0:a]atrim={b},asetpts=PTS-STARTPTS[y];"
           f"[x][y]concat=n=2:v=0:a=1,apad=pad_dur={gap}[o]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", flt, "-map", "[o]", "-c:a", "libmp3lame", "-q:a", "2", str(p)], check=True)
    src.unlink()
    print("ok", p.name, "cut", round(gap, 2), "s at", a)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
