"""Speech-to-text check of the voice takes: does the clone SAY the script line? (An alignment echo only repeats the input text.)

Usage: stt_check.py <story-name> <work-dir-name> [--fix]
Transcribes each picked take with faster-whisper (ONE job at a time, fleet rule), compares it to the line in <story>.vo.json, and reports
lines under SIMILAR. With --fix, a failing line is re-picked to whichever of its three takes matches best (picked.json is rewritten).
"""
import difflib
import json
import re
import sys
from pathlib import Path

from faster_whisper import WhisperModel

SIMILAR = 0.90
HERE = Path(__file__).parent
NUM = {"twenty-five": "25", "twenty five": "25", "twenty": "20", "fifteen": "15", "2011": "2011", "forty thousand dollar": "40000 dollar"}


CANON = [(r"\bseth\s*(?:sh|sch|s)\w*\b", "seth"), (r"\bsethshoultes\b", "seth"), (r"\b(?:dot )?(?:com|calm)\b", "com"),
         (r"\baccess\s*all(?:y|ey)\b", "accessally"), (r"\bmember\s*mouse\b", "membermouse"), (r"\bpretty\s*links\b", "prettylinks"),
         (r"\bhouse\s*call\b", "housecall"), (r"\bchat\s*gpt\b", "chatgpt"), (r"\bservice\s*titan\b", "servicetitan"),
         (r"\bevent\s*espresso\b", "eventespresso"), (r"\bllms\s*(?:dot\s*)?txt\b", "llmstxt"), (r"\bwish\s*list\b", "wishlist"), (r"\bsuper\s*pro\b", "superpro"), (r"\bweb side\b", "website")]


def norm(t):
    t = re.sub(r"\[[^\]]*\]", "", t.lower()).replace("\u2014", " ").replace("...", " ").replace("llms.txt", "llms txt")
    t = t.replace("$40,000", "40000 dollar").replace("40,000", "40000").replace("memberpress dot a i", "memberpress ai").replace("memberpress.ai", "memberpress ai")
    for k, v in NUM.items():
        t = t.replace(k, v)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    for pat, rep in CANON:
        t = re.sub(pat, rep, t)
    return t.split()


def diff_words(a, b):
    x, y = norm(a), norm(b)
    ops = difflib.SequenceMatcher(None, x, y).get_opcodes()
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in ops if tag != "equal")


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def main(name, workdir, fix):
    V = Path.home() / "work" / workdir / "vo"
    lines = {x["id"]: x["vo"] for x in json.load(open(HERE / "stories" / f"{name}.vo.json"))["shots"]}
    picked = json.load(open(V / "picked.json"))
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    cache = {}

    def say(f):
        if f not in cache:
            segs, _ = model.transcribe(str(V / f), language="en", beam_size=5)
            cache[f] = " ".join(s.text for s in segs).strip()
        return cache[f]

    bad = 0
    for i, text in lines.items():
        got = say(picked[i]["file"])
        r = sim(text, got)
        dw = diff_words(text, got)
        failing = dw >= (1 if len(norm(text)) <= 8 else 2)
        flag = "  <-- MISMATCH" if failing else ""
        print(f"{i} t{picked[i]['take']} {r:.2f} diff={dw}{flag}")
        if failing:
            bad += 1
            print(f"    script: {text}\n    heard : {got}")
            if fix:
                best = min(((diff_words(text, say(f"{i}-t{t}.mp3")), -sim(text, say(f"{i}-t{t}.mp3")), t) for t in (1, 2, 3) if (V / f"{i}-t{t}.mp3").exists()))
                print(f"    best take t{best[2]}: {best[0]} differing word(s): {say(f'{i}-t{best[2]}.mp3')}")
                if best[0] < dw:
                    picked[i] = dict(picked[i], take=best[2], file=f"{i}-t{best[2]}.mp3")
    if fix:
        json.dump(picked, open(V / "picked.json", "w"), indent=1)
    print(f"{name}: {bad} mismatching line(s)")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--fix"]
    if len(a) != 2:
        sys.exit(__doc__)
    main(a[0], a[1], "--fix" in sys.argv)
