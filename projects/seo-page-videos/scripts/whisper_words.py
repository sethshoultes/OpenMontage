"""Real word times for the picked takes: <take>.ww.json beside each picked mp3, read by build_story_video.py in place of the
alignment's character timings (those are spread over the file and can be a second out).

Usage: whisper_words.py <vo-dir>
Run with the cast venv python (faster-whisper): ~/projects/memberpress-ai-cast/.venv/bin/python. ONE job at a time (fleet rule).
Each alignment word gets the onset of the matching whisper word; words whisper merged or spelled differently (numbers) are
interpolated between their matched neighbours. Whisper onsets run about 0.15 s early; the builder's leads account for that.
"""
import difflib
import json
import re
import sys
import subprocess
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def align_words(chars):
    out, cur = [], ""
    for c in chars:
        if c.isspace():
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += c
    return out + ([cur] if cur else [])


def envelope(path):
    """Smoothed 20 ms voice energy (0..1) of a take at 100 frames/s."""
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float))
    a /= a.max()
    hop = 160
    n = len(a) // hop
    return a[: n * hop].reshape(n, hop).mean(axis=1)


def refine(start, end, env):
    """Whisper stretches a word's start back across the pause before it (even into the tail of the word before). The voice onset is the end
    of the last silence (energy under 2% of the take's peak for 80 ms or more) that falls inside the word's whisper span; with no silence
    inside, the start stands. A word whose span ends in silence is cut at the last frame with sound."""
    i0, i1 = int(start * 100), min(max(int(end * 100), int(start * 100) + 2), len(env) - 1)
    quiet = env[i0:i1 + 1] < 0.02
    onset, run = None, 0
    for k, q in enumerate(quiet):
        if q:
            run += 1
        else:
            if run >= 8:
                onset = (i0 + k) / 100
            run = 0
    t0 = onset if onset is not None else start
    k0 = int(t0 * 100)
    if k0 < len(env) and env[k0] < 0.02:   # the whole span sits in silence: the word is really said at the next rise (within 1.5 s)
        for k in range(k0, min(k0 + 150, len(env) - 3)):
            if (env[k:k + 3] >= 0.02).all():
                return k / 100
    return t0


def main(vo_dir):
    vo = Path(vo_dir)
    picked = json.load(open(vo / "picked.json"))
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    for sid, pk in sorted(picked.items()):
        mp3 = vo / pk["file"]
        al = json.load(open(str(mp3)[:-4] + ".json"))
        aw = align_words(al["characters"])
        segs, _ = model.transcribe(str(mp3), word_timestamps=True, language="en")
        env = envelope(mp3)
        ww, prev = [], -1.0
        for sg in segs:
            for w in sg.words:
                if norm(w.word):
                    t0 = refine(w.start, w.end, env)
                    if t0 < prev + 0.08:   # two words cannot start in the same silence: the later one keeps whisper's own start
                        t0 = max(w.start, prev + 0.08)
                    ww.append((norm(w.word), t0))
                    prev = t0
        a_n = [norm(w) for w in aw]
        sm = difflib.SequenceMatcher(None, a_n, [w for w, _ in ww], autojunk=False)
        t = [None] * len(aw)
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                t[blk.a + k] = ww[blk.b + k][1]
        known = [i for i, x in enumerate(t) if x is not None]
        if not known:
            sys.exit(f"{sid}: no word matched whisper")
        total = ww[-1][1]
        for i in range(len(t)):
            if t[i] is not None:
                continue
            lo = max((k for k in known if k < i), default=None)
            hi = min((k for k in known if k > i), default=None)
            if lo is None:
                t[i] = max(0.0, t[hi] - 0.3 * (hi - i))
            elif hi is None:
                t[i] = t[lo] + 0.3 * (i - lo)
            else:
                t[i] = t[lo] + (t[hi] - t[lo]) * (i - lo) / (hi - lo)
                k0 = int(t[i] * 100)
                if k0 < len(env) and env[k0] < 0.02:   # an unmatched word interpolated into a silence is said at the next rise
                    for k in range(k0, min(int(t[hi] * 100), len(env) - 3)):
                        if (env[k:k + 3] >= 0.02).all():
                            t[i] = k / 100
                            break
        json.dump({"words": [[w, round(x, 3)] for w, x in zip(aw, t)]}, open(str(mp3)[:-4] + ".ww.json", "w"))
        print(sid, "matched", len(known), "of", len(aw), "first %.2f" % t[0])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
