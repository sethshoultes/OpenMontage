"""List the silences over 0.45 s inside each picked take (not at its ends), with the words either side, so in-clause dead pauses can be cut
(trim_gap.py) before the designer pass. Sentence-end and ellipsis breaths show up too: judge by the words.

Usage: pause_check.py <vo-dir>
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def main(vo):
    vo = Path(vo)
    picked = json.load(open(vo / "picked.json"))
    for sid, pk in sorted(picked.items()):
        f = vo / pk["file"]
        raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(f), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
        a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float))
        a /= a.max()
        env = a[: len(a) // 160 * 160].reshape(-1, 160).mean(1)
        live = np.where(env > 0.02)[0]
        lo, hi = live[0], live[-1]
        ww = json.load(open(str(f)[:-4] + ".ww.json"))["words"]
        i = lo
        while i < hi:
            if env[i] < 0.02:
                j = i
                while j < hi and env[j] < 0.02:
                    j += 1
                if (j - i) >= 45:
                    before = [w for w, t in ww if t <= i / 100][-2:]
                    after = [w for w, t in ww if t >= j / 100][:2]
                    print(f"{sid} {i/100:5.2f}-{j/100:5.2f} ({(j-i)/100:.2f}s)  {' '.join(before)} | {' '.join(after)}")
                i = j
            else:
                i += 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
