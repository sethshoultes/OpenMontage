#!/usr/bin/env python3
"""The three render checks from the Ohmsville repo's docs/film-pipeline.md, each with its control.

    .venv/bin/python projects/ohmsville-classroom/scripts/check_render.py percepto

Those checks were run by hand on the Spooky Shack and on The Box, and re-derived from the doc's
prose each time. They are the pipeline's own gate, so they belong in the repo beside the compositor
rather than in a shell transcript:

  1. **The cut table is contiguous.** Every `out_seconds` equals the next `in_seconds`, the first
     cut opens at 0, and nothing overlaps.
  2. **No bare background between beats.** A previous trailer shipped with the theme ground showing
     at every cut, because the compositor advanced its clock without extending the video. Every
     frame is downsampled and scored for its share of theme-ground pixels.
  3. **The narration matches the picture.** Each section's rendered audio is transcribed and aligned
     against that section's own script line.
There is deliberately no fourth check on "how dark the picture goes at a cut", and the reason is
worth keeping. Check 2 only knows one colour, so a frame that went flat BLACK would sail through it,
and every seam in this film has 2-4 frames that measure ~96% one flat colour at luma ~1.5/255. That
looked like a second bug until the frames were opened and the luma ramp measured across a seam
(8.9, 8.3 | 1.4, 2.1, 4.2, 4.7, 6.4, 8.4, ... 13.1): it is `useFade`'s spring fade-in, and the board
really is there, at about 2% opacity. Both shipped films do the same thing. A frame at 2% opacity and
a frame with nothing drawn on it are statistically indistinguishable — measured side by side, the
true gap frame scored norm_std 0.097 and the legitimate fade-in frame 0.085 — because at that
opacity they are the same picture, to a scanner and to a viewer. So a flatness gate would fire on
correct behaviour, which is worse than no gate. The theme ground is the discriminating signal
precisely because nothing else in the film is that colour, which is why check 2 is written the way
it is rather than as "the frame went dark".

"A check that cannot fail is not a check" (video-guidelines.md), so each one runs a control that
must come out the other way round, and the run fails if a control does NOT behave as a failure:

  1. a deliberately punched hole in a copy of the cut table, which must be reported;
  2. a synthesized frame of pure theme ground pushed through the identical scorer, which must score
     ~1.000 and trip the threshold;
  3. one section's script aligned against a DIFFERENT section's audio, which must score far below
     the real pairs.

Exit status is 0 only if every check passed AND every control failed the way it was supposed to.
"""
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"

sys.path.insert(0, str(ROOT))
from tools.tool_registry import registry  # noqa: E402

# Downsample every frame to this before scoring. The bug being hunted is a whole-frame one — the
# ground showing through where a shot should be — so per-pixel detail is noise; this keeps a
# 150-second film's scan to a few hundred KB of pixels and a second of wall clock.
SCAN_W, SCAN_H = 64, 36
# Max share of a frame that may be theme ground. The real failure looked like a whole bare frame
# (~1.0); a legitimate frame carries the ground only as card backing behind art and text. Set well
# clear of both, and the run prints the observed max so the margin is visible rather than asserted.
GROUND_SHARE_LIMIT = 0.60
# Per-channel tolerance for "this pixel is the theme ground". Deliberately tight: the Night Shift
# board is itself a dark colour a dozen RGB units from #140c1c, so a loose tolerance would score a
# perfectly good board beat as bare. The run prints the real board's distance from the ground so
# this number can be seen to separate them rather than taken on faith.
GROUND_TOL = 6
# Below this, a section's audio is not saying that section's line. Real pairs on The Box scored
# ≥0.98; the cross-paired control scored 0.15. Numerals are the one honest gap — a script writes
# "Nineteen fifty-nine" and ASR hears "1959" — so this sits low enough to tolerate a few of those
# and nowhere near low enough to accept the wrong take.
ALIGN_MIN = 0.90
# A control pair must land below this, or the aligner is matching on something other than content.
CONTROL_MAX = 0.60


def hex_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def frames(path: Path, w: int = SCAN_W, h: int = SCAN_H) -> np.ndarray:
    """Every frame of `path` as an (n, h, w, 3) uint8 array, via one ffmpeg pipe."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(-1, h, w, 3)


def ground_share(frame: np.ndarray, ground: tuple[int, int, int]) -> float:
    """Share of this frame's pixels within GROUND_TOL of the theme ground, per channel."""
    d = np.abs(frame.astype(np.int16) - np.array(ground, dtype=np.int16))
    return float((d.max(axis=-1) <= GROUND_TOL).mean())


_NUMBER_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six",
    "7": "seven", "8": "eight", "9": "nine", "10": "ten", "11": "eleven", "12": "twelve",
    "13": "thirteen", "14": "fourteen", "15": "fifteen", "16": "sixteen", "17": "seventeen",
    "18": "eighteen", "19": "nineteen", "20": "twenty",
}
_TENS_WORDS = {
    2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty",
    9: "ninety",
}


def _spell_two_digit(n: int) -> str:
    """0-99 as the words a narrator would say, reusing `_NUMBER_WORDS` for the irregular teens."""
    if n < 20:
        return _NUMBER_WORDS[str(n)]
    tens, ones = divmod(n, 10)
    return _TENS_WORDS[tens] if ones == 0 else f"{_TENS_WORDS[tens]} {_NUMBER_WORDS[str(ones)]}"


def _spell_year(m: re.Match) -> str:
    """A four-digit year the way it is actually said: two two-digit pairs ("eighteen forty-one"),
    or "hundred" when the low pair is a bare century ("eighteen hundred")."""
    hi, lo = int(m.group(0)[:2]), int(m.group(0)[2:])
    return f"{_spell_two_digit(hi)} hundred" if lo == 0 else f"{_spell_two_digit(hi)} {_spell_two_digit(lo)}"


def normalise(text: str) -> list[str]:
    """Spoken words only: the leading delivery `[tag]` is stripped before synthesis, so it is not
    in the audio and must not be in the reference either.

    Three ASR-driven mismatches recur, none of them a script or audio defect, so they're fixed here
    rather than by touching Seth-approved narration text:

    - the boilerplate "...at ohmsville dot com" closer, marginal even on precedent films (Spooky
      Shack s7 scored 0.902, Percepto s8 0.952) and an outright FAIL on the inventor films' much
      shorter closing line: Whisper transcribes a spoken digit as a numeral ("10" not "ten") and
      renders spoken "dot com" as the literal punctuation ".com", silently dropping the "dot" token.
    - inventor-georg-ohm s4: Whisper transcribes a spoken century-style year ("eighteen forty-one")
      as a bare four-digit numeral ("1841"). inventor-alessandro-volta s3 and Ohm's own s3 say
      "eighteen twenty-seven" the same way and still passed only because the surrounding sentence is
      long enough to absorb one mismatched token; Ohm s4's sentence is short enough that the same gap
      alone dropped it from ~0.97 to 0.893, under the 0.90 threshold. `_spell_year` turns "1841" back
      into "eighteen forty one" so it lines up with the script the same way the 1-2 digit case does.

    The "ohmsville" vs "omsville" mishearing, and Ohm s4's own "Copley" heard as "Coply" (ASR
    confidence 0.276 on that one word), are left alone deliberately — hardcoding a specific
    word-for-word substitution would be overfit and could mask a real defect elsewhere. Ohm s4 scores
    comfortably clear of 0.90 once the year alone is fixed, so no second fix is needed for it to pass.
    """
    text = re.sub(r"^\s*\[[^\]]*\]\s*", "", text)
    text = re.sub(r"\.(com|org|net|io)\b", r" dot \1", text)
    text = re.sub(r"\b(1[0-9]|20)\d{2}\b", _spell_year, text)
    text = re.sub(r"\b\d{1,2}\b", lambda m: _NUMBER_WORDS.get(m.group(0), m.group(0)), text)
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split()


def align(script: str, heard: str) -> float:
    return SequenceMatcher(None, normalise(script), normalise(heard)).ratio()


def check_contiguity(cuts: list[dict]) -> list[str]:
    """Faults in a cut table: a first cut that does not open at 0, and any seam that is not exact."""
    faults = []
    if not cuts:
        return ["no cuts at all"]
    if abs(cuts[0]["in_seconds"]) > 1e-9:
        faults.append(f"first cut opens at {cuts[0]['in_seconds']}, not 0")
    for a, b in zip(cuts, cuts[1:]):
        if abs(a["out_seconds"] - b["in_seconds"]) > 1e-9:
            gap = b["in_seconds"] - a["out_seconds"]
            faults.append(f"{a['id']} -> {b['id']}: {'gap' if gap > 0 else 'overlap'} of {abs(gap):.2f}s")
    return faults


def main(trailer_id: str) -> int:
    art = PROJECT / "artifacts" / f"trailer-{trailer_id}"
    comp = json.loads((art / "composition.json").read_text())
    shotlist = json.loads((art / "_source_snapshot" / "shotlist.json").read_text())
    video = PROJECT / "renders" / trailer_id / "final.mp4"
    staged = ROOT / "remotion-composer" / "public" / "ohmsville-trailers" / trailer_id
    ok = True

    print(f"=== {trailer_id}: {video}")

    # ---- 1. the cut table is contiguous, and a punched hole is reported -----------------------
    cuts = comp["cuts"]
    faults = check_contiguity(cuts)
    print(f"\n[1] cut table: {len(cuts)} cuts, "
          f"{cuts[0]['in_seconds']:.2f} -> {cuts[-1]['out_seconds']:.2f}s")
    if faults:
        ok = False
        for f in faults:
            print(f"    FAIL {f}")
    else:
        print("    PASS every out_seconds == the next in_seconds, first opens at 0")
    holed = [dict(c) for c in cuts]
    holed[len(holed) // 2]["in_seconds"] += 0.5  # the exact bug: clock advanced, picture not
    control = check_contiguity(holed)
    print(f"    control (0.5s hole punched mid-table): "
          f"{'flagged — ' + control[0] if control else 'NOT FLAGGED'}")
    if not control:
        ok = False

    # ---- 2. no bare theme ground between beats, and a bare frame is caught --------------------
    ground = hex_rgb(comp["themeConfig"]["backgroundColor"])
    fs = frames(video)
    shares = np.array([ground_share(f, ground) for f in fs])
    worst = int(shares.argmax())
    fps = comp["fps"]
    print(f"\n[2] bare-background scan: {len(fs)} frames, ground {comp['themeConfig']['backgroundColor']} "
          f"= rgb{ground}, tolerance +/-{GROUND_TOL}")
    print(f"    max ground share {shares.max():.3f} at frame {worst} ({worst / fps:.2f}s); "
          f"mean {shares.mean():.3f}; limit {GROUND_SHARE_LIMIT}")
    if shares.max() > GROUND_SHARE_LIMIT:
        ok = False
        over = np.flatnonzero(shares > GROUND_SHARE_LIMIT)
        print(f"    FAIL {over.size} frame(s) over the limit, first at {over[0] / fps:.2f}s")
    else:
        print("    PASS no frame is mostly bare ground")
    # The control: a frame of nothing but ground, scored by the identical function.
    bare = np.tile(np.array(ground, dtype=np.uint8), (SCAN_H, SCAN_W, 1))
    bare_score = ground_share(bare, ground)
    print(f"    control (synthesized all-ground frame): scores {bare_score:.3f}, "
          f"{'flagged' if bare_score > GROUND_SHARE_LIMIT else 'NOT FLAGGED'}")
    if bare_score <= GROUND_SHARE_LIMIT:
        ok = False
    # And the separation the tight tolerance is buying: how far the real board sits from the ground.
    board = fs[len(fs) // 2].reshape(-1, 3).astype(np.int16)
    dist = np.abs(board - np.array(ground, dtype=np.int16)).max(axis=-1)
    print(f"    separation: mid-film frame sits a median {int(np.median(dist))} RGB units from the "
          f"ground (tolerance {GROUND_TOL}), so a real beat cannot score as bare")

    # ---- 3. each section's audio says that section's line, and a crossed pair does not ---------
    print(f"\n[3] narration alignment (threshold {ALIGN_MIN}):")
    heard: dict[str, str] = {}
    scores: dict[str, float] = {}
    for s in shotlist["sections"]:
        mp3 = staged / "narration" / f"{s['id']}.mp3"
        r = registry.get("transcriber").execute({"input_path": str(mp3),
                                                 "output_dir": str(art / "transcripts")})
        if not r.success:
            raise RuntimeError(f"transcriber failed on {mp3}: {r.error}")
        heard[s["id"]] = " ".join(w["word"] for w in r.data["word_timestamps"])
        scores[s["id"]] = align(s["narration"], heard[s["id"]])
        verdict = "PASS" if scores[s["id"]] >= ALIGN_MIN else "FAIL"
        if verdict == "FAIL":
            ok = False
        print(f"    {s['id']}  {scores[s['id']]:.3f}  {verdict}")
    ids = [s["id"] for s in shotlist["sections"]]
    a, b = ids[0], ids[len(ids) // 2]
    crossed = align(next(s["narration"] for s in shotlist["sections"] if s["id"] == a), heard[b])
    print(f"    control ({a}'s script vs {b}'s audio): {crossed:.3f}, "
          f"{'correctly rejected' if crossed < CONTROL_MAX else 'NOT REJECTED'}")
    if crossed >= CONTROL_MAX:
        ok = False

    print(f"\n=== {'ALL CHECKS PASS, ALL CONTROLS BEHAVED' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    registry.discover()
    sys.exit(main(sys.argv[1]))
