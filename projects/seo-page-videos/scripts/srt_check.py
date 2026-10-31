"""Check a rendered video's caption cues against the voice in the final mix.

Usage: srt_check.py <video.audio.m4a> <video.srt> [--fix <story.json>]
Transcribes the mix once (faster-whisper base.en, ONE job at a time; cast venv python) and prints, per cue, the cue start against the onset of
its first word (negative = the cue starts early; fine is -0.5 to +0.3). Whisper onsets run about 0.15 s early against a listener.
With --fix, writes the cue start that puts every out-of-window cue 0.25 s before its word into the story's "srt_at" list
([cue first words, seconds]); build_story_video.py applies it on the next render.
"""
import difflib
import json
import re
import sys
from pathlib import Path

from faster_whisper import WhisperModel


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def main(audio, srt, fix=None):
    segs, _ = WhisperModel("base.en", device="cpu", compute_type="int8").transcribe(audio, word_timestamps=True, language="en")
    ww = [(norm(w.word), w.start) for s in segs for w in s.words if norm(w.word)]
    cues = []
    for blk in Path(srt).read_text().strip().split("\n\n"):
        ln = blk.split("\n")
        a = ln[1].split(" --> ")[0]
        h, m, s = a.replace(",", ".").split(":")
        cues.append((int(ln[0]), float(h) * 3600 + float(m) * 60 + float(s), " ".join(ln[2:])))
    allw = [norm(w) for _, _, t in cues for w in t.split() if norm(w)]
    sm = difflib.SequenceMatcher(None, allw, [w for w, _ in ww], autojunk=False)
    onset = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            onset[blk.a + k] = ww[blk.b + k][1]
    pos, bad, edits = 0, 0, []
    for n, a, t in cues:
        words = [norm(w) for w in t.split() if norm(w)]
        o = onset.get(pos)
        pos += len(words)
        if o is None:
            print(f"{n:3d} {a:7.2f}  ?      {t[:50]}")
            continue
        d = a - o
        flag = "" if -0.5 <= d <= 0.3 else "  <-- OUT"
        bad += bool(flag)
        if flag:
            edits.append([" ".join(t.split()[:3]), round(o - 0.25, 2)])
        print(f"{n:3d} {a:7.2f} {d:+.2f}  {t[:50]}{flag}")
    print(f"{bad} cue(s) out of window")
    if fix and edits:
        p = Path(fix)
        d = json.load(open(p))
        d["srt_at"] = edits
        json.dump(d, open(p, "w"), indent=1)
        print("wrote srt_at to", fix)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) not in (2, 4) or (len(a) == 4 and a[2] != "--fix"):
        sys.exit(__doc__)
    main(a[0], a[1], a[3] if len(a) == 4 else None)
