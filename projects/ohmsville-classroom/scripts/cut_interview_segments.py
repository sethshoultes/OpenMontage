#!/usr/bin/env python3
"""Cut a documentary's interview segments out of the personas' own rendered profile films.

    python projects/ohmsville-classroom/scripts/cut_interview_segments.py people-of-ohmsville

New for #92's second film, and used by nothing else. Every other beat this pipeline renders is a
picture with narration laid over it; an `interview:` beat is the one kind whose audio was recorded
when that persona's own profile film was made. So it is not narrated, not looped, and not the
length of anything this repo computes — it is exactly as long as the piece of tape it comes from.

What it reads
-------------
The film's own edit decision list, `docs/films/<film>.edl.md` in the Ohmsville repo, which is the
one document that carries the in/out windows and the reasoning behind them. A row with a numeric
In and Out is an interview row; every other row is a picture and is skipped. The source is the
persona's `media/people/<slug>/heygen-raw.mp4` — the lip-synced download, deliberately NOT
`final.mp4`, which carries a title card over its first 2.5s, a lower third from 3.5s to 9.5s and a
3s appended end card, all of which would land inside a segment at the wrong moment.

Why the In is snapped
---------------------
The EDL's In is derived: the manifest's per-section seconds plus the 0.6s `anullsrc` gaps that
build-narration.ts's concat put between sections, corrected for a per-section over-read of about
0.066s (that document's own "Where the In and Out numbers come from" section has the measurements).
The correction is good to a few hundredths, which is smaller than a syllable but not zero — and the
one place it must not be wrong is the first frame of speech. So each In is snapped to the silence
that precedes it: `silencedetect` over a +/-SNAP_WINDOW second window, take the last silence ending
inside it, and start LEAD_IN seconds before that silence ends. No silence in the window means the
derived number stands, and the segment says so in its own record.

What it writes, into the film's asset directory beside its stills
-----------------------------------------------------------------
  <slug>-<section>.mp4   the picture, normalised to the delivered 1920x1080 at 30fps
  <slug>-<section>.mp3   the same segment's audio alone, which is what build_trailer.py lays into
                         the narration bed in place of a clip it would otherwise have bought
  segments.json          every window actually cut, what it was snapped from and to, and the
                         measured duration of the result — the file build_trailer.py reads, so the
                         cut and the render can never disagree about how long a beat is

Idempotent: a segment whose recorded window and source mtime are unchanged is not re-cut.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
OHMSVILLE = Path(os.environ.get("OHMSVILLE_REPO", "~/projects/circuit-city-trailer")).expanduser()
# The interview films are gitignored binaries: they live in one checkout of the repo whatever
# branch anybody is on, so a worktree building this film reads them from wherever they really
# are rather than from its own empty media/ directory. Defaults to the repo it was given.
MEDIA = Path(os.environ.get("OHMSVILLE_MEDIA", str(OHMSVILLE / "media"))).expanduser()

# How far either side of the derived In to look for the silence the speech starts out of. The
# derived number's own residual is a few hundredths of a second (see the EDL); 0.2 is an order of
# magnitude more room than that, and still far too narrow to reach the previous sentence.
SNAP_WINDOW = 0.20
# Start this far before the silence ends, so the first consonant is never clipped. A plosive's
# closure reads as silence to silencedetect, and 60ms is comfortably longer than one.
LEAD_IN = 0.06
# -35dB over 60ms: the gaps here are a synthesised `anullsrc` between two rendered clips, so they
# are true digital silence, not room tone. A threshold this generous finds them without hunting
# for pauses inside a sentence.
SILENCE_DB = -35
SILENCE_MIN = 0.06

FRAME = (1920, 1080)
FPS = 30


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {' '.join(cmd[1:6])}...\n{proc.stderr[-2000:]}")
    return proc


def ffprobe_duration(path: Path) -> float:
    proc = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path)])
    return float(proc.stdout.strip())


def edl_rows(film: str):
    """Every interview row of the film's EDL: its beat id, source film and section, and its window.

    The table is `| At | Beat | Source | In | Out | Dur | First words |`. A picture row carries an
    em dash in In and Out and does not match, which is the same distinction
    client/tests/edl.test.ts draws on the same table.
    """
    src = (OHMSVILLE / "docs" / "films" / f"{film}.edl.md").read_text()
    rows = []
    pattern = (r"^\| (\d\d:\d\d) \| (s\d+) . ([^|]+?) \| `(profile-[a-z-]+) (s\d+)` \| "
               r"([\d.]+) \| ([\d.]+) \| ([\d.]+) \|")
    for at, beat, label, profile, section, t_in, t_out, dur in re.findall(pattern, src, re.M):
        rows.append({
            "id": beat, "label": label.strip(), "profile": profile, "section": section,
            "slug": profile[len("profile-"):],
            "in": float(t_in), "out": float(t_out), "edl_seconds": float(dur), "at": at,
        })
    if not rows:
        raise RuntimeError(f"no interview rows found in docs/films/{film}.edl.md — the table's "
                           f"shape must have changed; this script reads it, it does not guess")
    return rows


def snap_in(source: Path, nominal: float):
    """The real start of this section's speech, and how it was decided.

    Returns the cut point and a one-line account of it, which goes into segments.json so a reader
    can tell a measured snap from a fallback without re-running anything.
    """
    lo = max(0.0, nominal - SNAP_WINDOW)
    span = (nominal + SNAP_WINDOW) - lo
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{lo:.3f}", "-t", f"{span:.3f}", "-i", str(source),
         "-af", f"silencedetect=n={SILENCE_DB}dB:d={SILENCE_MIN}", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    # silencedetect reports times relative to the trimmed input, so they are offsets into the
    # window and have to be put back onto the source's own clock.
    ends = [lo + float(x) for x in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    inside = [e for e in ends if lo <= e <= nominal + SNAP_WINDOW]
    if not inside:
        return nominal, f"no silence within +/-{SNAP_WINDOW}s; derived In kept"
    end = max(inside)
    cut_at = max(0.0, end - LEAD_IN)
    return cut_at, (f"silence ends {end:.3f}s, cut {LEAD_IN}s earlier "
                    f"({cut_at - nominal:+.3f}s from derived)")


def cut(row, source: Path, dest_dir: Path):
    stem = f"{row['slug']}-{row['section']}"
    mp4 = dest_dir / f"{stem}.mp4"
    mp3 = dest_dir / f"{stem}.mp3"
    start, how = snap_in(source, row["in"])
    # The out stays where the EDL put it: the end of a segment lands in the gap after the last
    # word, where a few hundredths either way is inaudible, and snapping both ends would let a
    # segment's length drift away from the number the cut plan is holding.
    length = row["out"] - start

    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(source),
         # cover, not stretch — the same normalisation loop_clip applies to a generated clip, so a
         # talking head and a generated scene are the same shape in the delivered frame.
         "-vf", f"scale={FRAME[0]}:{FRAME[1]}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={FRAME[0]}:{FRAME[1]},fps={FPS}",
         "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-movflags", "faststart", str(mp4)])
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(source),
         "-vn", "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-q:a", "4", str(mp3)])

    v, a = ffprobe_duration(mp4), ffprobe_duration(mp3)
    if abs(v - a) > 0.12:
        raise RuntimeError(f"{stem}: picture runs {v:.3f}s and audio {a:.3f}s — a talking head "
                           f"whose mouth and voice are different lengths is not usable")
    return {
        **row, "file": mp4.name, "audio": mp3.name,
        "source": str(source), "source_mtime": source.stat().st_mtime,
        "cut_in": round(start, 3), "cut_out": round(row["out"], 3),
        "snap": how, "video_seconds": round(v, 3), "audio_seconds": round(a, 3),
    }


def main(film: str) -> None:
    dest_dir = PROJECT / "assets" / "art" / film
    dest_dir.mkdir(parents=True, exist_ok=True)
    record = dest_dir / "segments.json"
    # Keyed by film and section, never by beat id. A beat id is a position in one draft of one
    # script: draft 2 of this film inserted five beats of scene-setting at the front and every id
    # after them moved, which silently orphaned all seven segments and failed the render. What a
    # segment IS, on the other hand, never changes — it is a section of somebody's profile film.
    prior = ({f'{x["profile"]} {x["section"]}': x for x in json.loads(record.read_text())["segments"]}
             if record.is_file() else {})

    segments = []
    for row in edl_rows(film):
        source = MEDIA / "people" / row["slug"] / "heygen-raw.mp4"
        if not source.is_file():
            raise RuntimeError(f"{row['id']}: no interview film at {source}")
        was = prior.get(f'{row["profile"]} {row["section"]}')
        fresh = bool(was and was["in"] == row["in"] and was["out"] == row["out"]
                     and was.get("source_mtime") == source.stat().st_mtime
                     and (dest_dir / was["file"]).is_file() and (dest_dir / was["audio"]).is_file())
        if fresh:
            # The cut is reusable; the beat it plays in is not. `id`, `label` and `at` describe
            # where this segment sits in the CURRENT script, and draft 2 renumbered every beat, so
            # returning the stored record verbatim leaves the record naming beats that no longer
            # exist. Refresh the positional fields and keep the measured ones.
            segments.append({**was, "id": row["id"], "label": row["label"], "at": row["at"],
                             "edl_seconds": row["edl_seconds"]})
            print(f"  {row['id']}  {was['file']}  {was['audio_seconds']:.2f}s  (already cut)")
            continue
        seg = cut(row, source, dest_dir)
        segments.append(seg)
        print(f"  {row['id']}  {seg['file']}  {seg['audio_seconds']:.2f}s  {seg['snap']}")

    record.write_text(json.dumps({"film": film, "segments": segments}, indent=2) + "\n")
    total = sum(s["audio_seconds"] for s in segments)
    print(f"{film}: {len(segments)} interview segments, {total:.2f}s, recorded in {record}")


if __name__ == "__main__":
    main(sys.argv[1])
