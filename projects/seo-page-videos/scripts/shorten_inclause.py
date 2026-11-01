"""Shorten the in-clause pauses of one voice take to a breath, reading the audio as it is now (no stale word times).

Usage: shorten_inclause.py <take.mp3> [keep_s=0.35] [min_s=0.5] [force_t,...]
force_t: times (s, in the take as it is) of silences to shorten even where whisper punctuated a sentence end
A silence of at least min_s is shortened to keep_s unless the word before it ends a sentence (whisper's own punctuation: . ? !, but not "...").
The take before this run is kept beside it as <take>.preshort.mp3 (copied once). Run whisper_words.py on the vo dir afterwards.
Run with the cast venv python (faster-whisper). ONE whisper job at a time (fleet rule).
"""
import difflib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from faster_whisper import WhisperModel


def silences(path, min_s):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", f"silencedetect=noise=-38dB:d={min_s}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))


def script_ends(words):
    """If env LINE holds the script line, map each whisper word to its script token so the script's own punctuation decides the sentence ends."""
    line = os.environ.get("LINE")
    if not line:
        return None
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    toks = line.split()
    a, b = [norm(w.word) for w in words], [norm(t) for t in toks]
    m = {}
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            m[blk.a + k] = toks[blk.b + k]
    return m


def main(mp3, keep=0.35, min_s=0.5, force=()):
    p = Path(mp3)
    pre = p.with_suffix(".preshort.mp3")
    if not pre.exists():
        shutil.copy(p, pre)
    sil = silences(p, min_s)
    segs, _ = WhisperModel("base.en", device="cpu", compute_type="int8").transcribe(str(p), word_timestamps=True, language="en")
    words = [w for s in segs for w in s.words]
    cuts = []
    smap = script_ends(words)
    for a, b in sil:
        prev = [w for w in words if w.end <= a + 0.25]
        tok = prev[-1].word.strip() if prev else ""
        if smap is not None and prev:
            tok = smap.get(words.index(prev[-1]), tok)
        if os.environ.get("KEEP_ELLIPSIS") and tok.endswith("..."):
            continue
        forced = any(a <= f <= b for f in force)
        if not forced and (not prev or re.search(r"((?<!\.)\.|\?|!)$", tok)):
            continue
        if b - a <= keep + 0.05:
            continue
        cuts.append((round(a + keep, 3), round(b, 3), tok))
    if not cuts:
        print(p.name, "nothing to shorten")
        return
    parts, t, n = [], 0.0, 0
    for a, b, _ in cuts:
        parts.append(f"[0:a]atrim={t}:{a},asetpts=PTS-STARTPTS[p{n}]")
        t, n = b, n + 1
    parts.append(f"[0:a]atrim={t},asetpts=PTS-STARTPTS[p{n}]")
    flt = ";".join(parts) + ";" + "".join(f"[p{i}]" for i in range(n + 1)) + f"concat=n={n + 1}:v=0:a=1[o]"
    tmp = p.with_suffix(".tmp.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-filter_complex", flt, "-map", "[o]", "-c:a", "libmp3lame", "-q:a", "2", str(tmp)], check=True)
    shutil.move(tmp, p)
    for a, b, tok in cuts:
        print(p.name, f"cut {a}-{b} after {tok!r}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    force = [float(x) for x in a[3].split(",")] if len(a) > 3 else []
    main(a[0], *(float(x) for x in a[1:3]), force=force)
