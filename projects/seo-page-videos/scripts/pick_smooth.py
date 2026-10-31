"""Re-pick each line's take for the smoothest read: the take with the least silence inside the line (pauses longer than 0.45 s).

Usage: pick_smooth.py <vo-dir> [<story-name> <work-dir-name>]
Dead air inside a clause reads as a hesitation; the script's own ellipses give every take a similar breath, so the take with the least
extra silence wins. Run it after gen_vo.py; run stt_check.py --fix afterwards and keep any take it does not reject (it only
re-picks a take that SAYS something different). Rewrites picked.json (the takes' own files are untouched).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def inner_silence(path):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float))
    a /= a.max()
    w = int(0.02 * 16000)
    sil = np.convolve(a, np.ones(w) / w, "same") < 0.02
    idx = np.where(~sil)[0]
    lo, hi = idx[0], idx[-1]
    total, cur = 0.0, 0
    for i in range(lo, hi):
        if sil[i]:
            cur += 1
        else:
            if cur / 16000 > 0.45:
                total += cur / 16000
            cur = 0
    return total


def main(vo_dir):
    vo = Path(vo_dir)
    picked = json.load(open(vo / "picked.json"))
    for sid, pk in sorted(picked.items()):
        score = {}
        for t in (1, 2, 3):
            f = vo / f"{sid}-t{t}.mp3"
            if f.exists():
                score[t] = inner_silence(f)
        best = min(score, key=score.get)
        print(sid, {t: round(v, 2) for t, v in score.items()}, "->", best)
        pk["take"], pk["file"] = best, f"{sid}-t{best}.mp3"
    json.dump(picked, open(vo / "picked.json", "w"), indent=1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
