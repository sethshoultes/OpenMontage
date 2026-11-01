"""Cut the in-clause dead pauses out of every picked take, then take the pad off the tails (trim_gap.py + trim_tail.py).

Usage: auto_trim_pauses.py <story-name> <vo-dir> [keep_s=0.35] [min_s=0.5]
A silence of at least min_s inside a take is an in-clause pause when the script word before it does not end a sentence or breath
('.', '?', '!', '...', ':'). Those are cut to keep_s; sentence-level breaths are left alone. Run whisper_words.py afterwards.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent


def silences(path, min_s):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float))
    a /= a.max()
    env = a[: len(a) // 160 * 160].reshape(-1, 160).mean(1)
    live = np.where(env > 0.02)[0]
    lo, hi = live[0], live[-1]
    out, i = [], lo
    while i < hi:
        if env[i] < 0.02:
            j = i
            while j < hi and env[j] < 0.02:
                j += 1
            if (j - i) >= int(min_s * 100):
                out.append((i / 100, j / 100))
            i = j
        else:
            i += 1
    return out


def main(name, vo, keep=0.35, min_s=0.5):
    vo = Path(vo)
    lines = {x["id"]: re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", x["vo"])).strip() for x in json.load(open(HERE / "stories" / f"{name}.vo.json"))["shots"]}
    picked = json.load(open(vo / "picked.json"))
    for sid, pk in sorted(picked.items()):
        f = vo / pk["file"]
        toks = lines[sid].split()
        ww = json.load(open(str(f)[:-4] + ".ww.json"))["words"]
        cuts = []
        for a, b in silences(f, min_s):
            before = [k for k, (w, t) in enumerate(ww) if t <= a]
            if not before or len(toks) != len(ww):
                continue
            tok = toks[before[-1]]
            if re.search(r"((?<!\.)\.|\?|!)$", tok):
                continue
            cuts.append((round(a + keep, 2), round(b, 2), tok))
        for a, b, tok in sorted(cuts, reverse=True):
            print(sid, f"cut {a}-{b} after {tok!r}")
            subprocess.run([sys.executable, str(HERE / "trim_gap.py"), str(f), str(a), str(b)], check=True, stdout=subprocess.DEVNULL)
        if cuts:
            subprocess.run([sys.executable, str(HERE / "trim_tail.py"), str(f)], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    main(a[0], a[1], *(float(x) for x in a[2:]))
