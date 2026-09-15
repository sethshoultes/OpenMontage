#!/usr/bin/env python3
"""Build one Ohmsville classroom lesson video from the Ohmsville repo's shot list.

    python projects/ohmsville-classroom/scripts/build_lesson.py what-electricity-is
    OHMSVILLE_REPO=~/projects/circuit-city python projects/ohmsville-classroom/scripts/build_lesson.py what-electricity-is

The Ohmsville repo owns the script, the narration and the footage; this owns the cut and the render.
Assets are copied under remotion-composer/public/ because Remotion's <Audio> rejects file:// URLs and
the space in "Local Sites" makes absolute URIs fragile (neural-networks-learn hit exactly this).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
# Overridable: the classroom-video-series work currently lives on the Ohmsville
# repo's "classroom-videos" worktree (checked out at circuit-city-video; the repo
# itself is still named circuit-city on GitHub). That worktree is transient — the
# lead deletes it after merging to master (see that repo's CLAUDE.md) — and its
# client/.shots/ output is gitignored, so it only ever exists wherever the shot
# recorder actually ran. Never hardcode it as a permanent path.
OHMSVILLE = Path(os.environ.get("OHMSVILLE_REPO", "~/projects/circuit-city-video")).expanduser()
PUBLIC = ROOT / "remotion-composer" / "public" / "ohmsville"

sys.path.insert(0, str(ROOT))
from tools.tool_registry import registry  # noqa: E402
from tools.subtitle.caption_align import align_words_to_reference  # noqa: E402

registry.discover()

THEME = {
    "primaryColor": "#a03020", "accentColor": "#ffd21f", "backgroundColor": "#241c10",
    "surfaceColor": "#f6eed8", "textColor": "#f0e2c0", "mutedTextColor": "#8a7a58",
    "headingFont": "Oswald", "bodyFont": "Georgia", "captionHighlightColor": "#ffd21f",
    "captionBackgroundColor": "rgba(36,28,16,0.82)",
}
# Kept alongside THEME (not read from artifacts/proposal_packet.json, which is
# gitignored/untracked per this repo's projects/*/ convention — reading it here
# would raise FileNotFoundError on any checkout that only has scripts/
# committed). Keep this string in sync with that packet's production_plan.art_direction
# by hand; it's short and changes rarely.
ART_DIRECTION = (
    "Science Fair '78: deep brown-black ground (#241c10), warm gold rule/accent "
    "(#ffd21f), oxide-red accent (#a03020), parchment surface (#f6eed8) for "
    "schematic cards, Oswald headings over Georgia body text."
)
# One music bed under every lesson in the series (the lead's ruling, 2026-09-15 —
# see main()'s music section below for the full reasoning). Generated once, saved
# here as a permanent series asset following this repo's own convention.
SERIES_MUSIC = PROJECT / "assets" / "music" / "background_music.mp3"
# A trailing gap after every narration clip, including the last — a stylistic
# choice (breathing room between lines), not something derived from the
# shotlist. record-shots.ts's own `startSeconds`/`totalSeconds` assume this
# same 0.4s gap, but its per-clip *duration* (`audioSeconds`, from a hand-rolled
# MPEG frame-header walker in build-narration.ts) measures every real
# ElevenLabs clip ~0.055-0.075s LONGER than what ffmpeg actually decodes —
# confirmed against all 9 real Lesson 1 clips. Accumulating startSeconds
# therefore accumulates that per-clip error too (-0.55s by section 9 on real
# data). Rather than trust either repo's precomputed number, this script
# derives the whole timeline from each clip's OWN locally-measured (ffprobe)
# duration once it's staged — see main()'s loop.
SECTION_GAP_SECONDS = 0.4

# Extra caption-box clearance (px, on a 1920x1080 frame) for sections whose
# recorded footage includes a `hover` step (client/src/classroom/videoScript.ts's
# ShotStep) — the bench's own hover-reading card renders as a fixed-position
# overlay along the bottom of the frame, baked into the video pixels, which
# the compositor can't move or hide. Measured directly against a real frame
# from the current (2026-09-15 framing-fix) recording: the card spans roughly
# y=884-966 of 1080; the default caption box (paddingBottom 80, ~90px tall)
# sits at y~910-1000, squarely on top of it. +140px moves the caption's
# bottom edge to y~860, clearing the card with margin. Cross-checked at two
# different hover moments (s3's "hover led-red", s4's "hover battery") — same
# card position both times, confirming it's fixed regardless of which part
# is hovered, so one measured constant covers every hover-bearing section.
HOVER_CAPTION_LIFT_PX = 140


def hover_sections(lesson: str) -> set[str]:
    """Which section ids have a `hover` step in their on-screen (post `>>`) take.

    shotlist.json (the recorder's OUTPUT) only keeps the final trimmed clip
    file per section — none of the individual ShotStep detail (press/hold/
    hover/linger) survives into it. The only place that detail still exists
    is the human-authored source script this section's shot was recorded
    from, content/videos/<lesson>.md, parsed structurally by videoScript.ts
    into ShotStep objects. Reading it directly here (not modifying it, and
    not reimplementing its Zod-adjacent validation, just checking for the
    `hover` token after a section's `>>`) is the only way to know which
    sections' visible footage carries a hover card, without changing
    record-shots.ts to propagate that flag into shotlist.json itself.
    """
    md_path = OHMSVILLE / "content" / "videos" / f"{lesson}.md"
    if not md_path.exists():
        return set()
    hover_ids: set[str] = set()
    current_id = None
    for line in md_path.read_text().splitlines():
        heading = re.match(r"^##\s+(s\d+)\s*[·:]", line)
        if heading:
            current_id = heading.group(1)
            continue
        if current_id and line.startswith("shot:"):
            take = line.split(">>", 1)[1] if ">>" in line else ""
            if re.search(r"\bhover\b", take):
                hover_ids.add(current_id)
            current_id = None
    return hover_ids


def run_ffmpeg(cmd: list[str]) -> None:
    """subprocess.run wrapper that prints stderr before re-raising on failure —
    check=True + capture_output=True alone buries a real ffmpeg error inside
    an unprinted CalledProcessError.stderr, leaving only "exited 1" to debug."""
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(e.stderr, file=sys.stderr)
        raise


def ffprobe_duration(path: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    ).strip())


def stage(lesson: str) -> Path:
    out = PUBLIC / lesson
    if out.exists():
        shutil.rmtree(out)
    (out / "narration").mkdir(parents=True)
    (out / "shots").mkdir()
    (out / "cards").mkdir()
    return out


def captions(section, audio_path, transcript_dir):
    """Words from our script, timing from ASR. Never the other way round (commit 6f8317bb).

    align_words_to_reference() takes/returns (word, start, end) TUPLES, not dicts —
    see tools/subtitle/caption_align.py and its real callers (build_launch.py,
    build_hero.py, build_short.py). transcriber.execute() input is `input_path`
    (not `audio_path`), and its word timings come back at
    result.data["word_timestamps"], each a dict — converted to tuples here for
    align_words_to_reference, then back to the caption dict shape on the way out.
    output_dir is pointed at artifacts/, not the Remotion public dir — otherwise
    the transcriber's own `<id>_transcript.json` writes ship into the composer's
    public/ tree alongside the real staged assets.
    """
    result = registry.get("transcriber").execute({
        "input_path": str(audio_path),
        "output_dir": str(transcript_dir),
    })
    if not result.success:
        raise RuntimeError(f"transcriber failed for {audio_path}: {result.error}")
    whisper_words = [(w["word"], w["start"], w["end"]) for w in result.data["word_timestamps"]]
    reference_words = section["narration"].split()
    aligned = align_words_to_reference(whisper_words, reference_words)
    return [{"word": word, "startMs": int(start * 1000), "endMs": int(end * 1000)}
            for word, start, end in aligned]


def main(lesson: str) -> None:
    art = PROJECT / "artifacts" / lesson
    transcript_dir = art / "transcripts"
    art.mkdir(parents=True, exist_ok=True)

    # Snapshot the Ohmsville repo's shot output immediately, before any slow
    # work (transcription, ffmpeg, the render itself) — that directory is
    # actively written by the shot recorder, which was observed re-running
    # and replacing its own output out from under this exact script while
    # iterating on a fill-policy/crop fix. A plain shutil.copytree() is NOT
    # enough on its own: it snapshots the directory LISTING at the instant it
    # starts, so if the recorder had already deleted shotlist.json (writing
    # it last, after all shot files, per its own cycle) but not yet
    # recreated it, copytree raises nothing — it just never attempted to
    # copy a file that, from its point of view, was never there. That
    # silently produced a snapshot missing shotlist.json with no exception
    # at all (caught only because the very next line failed to read it).
    # So: copy, then explicitly VALIDATE the copy (shotlist.json exists and
    # parses, and every section's shot file is present and non-trivial in
    # size) before trusting it, retrying the whole snapshot if not.
    live_shots = OHMSVILLE / "client" / ".shots" / lesson
    shots = art / "_source_snapshot"
    shotlist = None
    for attempt in range(5):
        try:
            if shots.exists():
                shutil.rmtree(shots)
            shutil.copytree(live_shots, shots)
            shotlist = json.loads((shots / "shotlist.json").read_text())
            missing = [
                s["shot"]["file"] for s in shotlist["sections"]
                if s.get("shot") and not (shots / s["shot"]["file"]).is_file()
            ]
            if missing:
                raise FileNotFoundError(f"snapshot missing shot file(s): {missing}")
            break
        except (FileNotFoundError, json.JSONDecodeError, shutil.Error, KeyError) as e:
            shotlist = None
            if attempt == 4:
                raise RuntimeError(
                    f"could not get a complete, stable snapshot of {live_shots} after "
                    f"5 tries — the shot recorder is still actively rewriting it: {e}"
                ) from e
            print(f"snapshot attempt {attempt + 1} caught the recorder mid-write ({e}); retrying in 5s", file=sys.stderr)
            time.sleep(5)
    out = stage(lesson)

    hover_ids = hover_sections(lesson)

    cuts, words = [], []
    sections = shotlist["sections"]
    t = 0.0
    for i, s in enumerate(sections):
        audio = out / "narration" / f"{s['id']}.mp3"
        shutil.copy(s["audio"], audio)
        lift = HOVER_CAPTION_LIFT_PX if s["id"] in hover_ids else 0

        # Timeline comes from THIS clip's own locally-measured duration, not
        # shotlist.json's startSeconds/audioSeconds (both computed upstream by
        # record-shots.ts/build-narration.ts's mp3Seconds(), which measures
        # every real ElevenLabs clip ~0.06s longer than ffmpeg actually decodes
        # it — verified against all 9 real Lesson 1 clips). Deriving start/end
        # from the exact bytes we're about to concatenate means the timeline
        # and the audio bed can't disagree, regardless of what either upstream
        # tool computed.
        real_dur = ffprobe_duration(audio)
        start = t
        end = start + real_dur
        t = end + SECTION_GAP_SECONDS
        for w in captions(s, audio, transcript_dir):
            words.append({"word": w["word"], "startMs": int(start * 1000) + w["startMs"],
                          "endMs": int(start * 1000) + w["endMs"], "liftPx": lift})

        if s["shot"]:
            shutil.copy(shots / s["shot"]["file"], out / "shots" / s["shot"]["file"])
            cuts.append({
                "id": s["id"], "type": "video", "layer": 0,
                "src": f"ohmsville/{lesson}/shots/{s['shot']['file']}",
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "sourceStartSeconds": s["shot"]["trimStartSeconds"],
                "label": s["label"],
            })
        elif s["card"]["kind"] == "schematic":
            shutil.copy(shots / s["card"]["file"], out / "cards" / s["card"]["file"])
            cuts.append({"id": s["id"], "type": "card", "layer": 0,
                         "src": f"ohmsville/{lesson}/cards/{s['card']['file']}",
                         "in_seconds": round(start, 2), "out_seconds": round(end, 2), "label": s["label"]})
        elif s["card"]["kind"] == "end" and cuts:
            # The shotlist's final section is card:end with no shot of its own —
            # its narration ("...waiting for you at ohmsville.com/classroom...")
            # is meant as the end card's voiceover, but rendering the end-card
            # PLATE for the full length of that narration puts the plate up
            # while a voice is still mid-sentence, with no silent beat
            # afterward to actually read it (caught by watching the real
            # render, not by any timing arithmetic — every number here is
            # frame-accurate; this is an ordering/pacing choice, not a
            # rounding bug). Fix: hold the PREVIOUS visual (last real shot)
            # through this section's own narration instead of cutting to the
            # end card yet, then let OhmsvilleLesson.tsx's own synthesis (see
            # its hasEndCut check) add the actual end-card plate — silent,
            # after narration ends — using endCard.seconds below. This also
            # restores the original spec's calculateMetadata behavior
            # (max(cuts.out_seconds) + endCard.seconds), which an earlier
            # round's hasEndCut fix had zeroed out for every real lesson that
            # ends this way.
            cuts[-1]["out_seconds"] = round(end, 2)
        else:
            # Covers the remaining CardKind values (title, none-with-no-shot,
            # or "end" with no prior cut to hold on — first-section edge case).
            cuts.append({"id": s["id"], "type": s["card"]["kind"], "layer": 0,
                         "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                         "title": shotlist["title"], "subtitle": "Intro to Electronics · Ohmsville",
                         "url": shotlist["lessonUrl"], "label": s["label"]})

    # One narration bed: each clip followed by a real SECTION_GAP_SECONDS of
    # silence (including after the last clip, matching the `t` accumulation
    # above). Built with ffmpeg's `concat` audio FILTER (decode-and-re-encode
    # once), not the concat DEMUXER's `-c copy` — stream-copying several
    # independently LAME-encoded MP3s introduces ~20-50ms of encoder
    # priming/padding at EVERY splice point (verified empirically: 3 clips +
    # 3 gaps came out ~0.19s long against nominal), which would reintroduce a
    # smaller version of the same class of drift this fix exists to remove.
    # The filter graph decodes every input to PCM and re-encodes the whole bed
    # as one continuous stream, so there's no per-file boundary left to drift
    # at (verified: exact match against nominal duration to the millisecond,
    # and 0.000s drift against the real 9-clip Lesson 1 narration).
    # _silence.mp3 lives under artifacts/, not the Remotion public/ tree — it's
    # a build-time fixture, never referenced by any composition prop.
    silence = art / "_silence.mp3"
    run_ffmpeg(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", str(SECTION_GAP_SECONDS), "-c:a", "libmp3lame", "-q:a", "6", str(silence)]
    )
    concat = out / "narration" / "full.mp3"
    inputs = []
    for s in sections:
        inputs += ["-i", str(out / "narration" / f"{s['id']}.mp3"), "-i", str(silence)]
    n = len(sections) * 2
    filter_graph = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    run_ffmpeg(
        ["ffmpeg", "-y", *inputs, "-filter_complex", filter_graph, "-map", "[out]",
         "-c:a", "libmp3lame", "-q:a", "4", str(concat)]
    )

    # Sanity check: compare the bed we just built against `t` — OUR OWN
    # running total, accumulated from the same locally-measured per-clip
    # durations and the same SECTION_GAP_SECONDS used to build it — not
    # shotlist.json's totalSeconds (which is itself computed from the
    # upstream repo's inflated audioSeconds and legitimately disagrees with
    # the real audio by design, see the comment above the loop). This checks
    # that the concat construction itself is self-consistent (e.g. no
    # off-by-one in `inputs`/`filter_graph`), not that it matches a number
    # this script has already established is unreliable.
    full_duration = ffprobe_duration(concat)
    if abs(full_duration - t) > 0.15:
        raise RuntimeError(
            f"narration bed duration {full_duration:.3f}s does not match "
            f"this script's own computed timeline total {t:.3f}s — the concat "
            f"construction has a bug, cut/caption placement would be wrong "
            f"against the actual audio"
        )

    total_seconds = max(c["out_seconds"] for c in cuts) if cuts else 0.0

    # Music: the series' one shared bed, by the lead's explicit ruling
    # (2026-09-15) — this is a deliberate identity choice for the whole
    # classroom series, not just a cost saving. Generated once, for
    # what-electricity-is's v3 render ($0.2983, ElevenLabs music_gen,
    # calm-workshop instrumental prompt), and saved permanently at
    # SERIES_MUSIC (following this repo's own convention for a project's
    # reusable background track — see projects/neural-networks-learn/assets/
    # music/background_music.mp3 and every projects/memberintel-*/assets/
    # music/background_music.mp3, same path shape). No pixabay_music call
    # here at all: a per-lesson pixabay success would hand some lessons a
    # *different* track than the rest, which is exactly what the ruling
    # says not to do, and pixabay_music's scrape already proved unreliable
    # (a real HTTP 403 during this project). Every lesson loops/trims this
    # same file to its own runtime, so marginal music cost per lesson is
    # $0 and there is no network dependency for music at all.
    if not SERIES_MUSIC.exists():
        raise RuntimeError(
            f"series music bed missing at {SERIES_MUSIC} — it must be generated once "
            f"(see the fix report for how) and saved there before any lesson can render"
        )
    run_ffmpeg([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(SERIES_MUSIC),
        "-t", f"{total_seconds:.3f}", "-c:a", "libmp3lame", "-q:a", "4",
        str(out / "music.mp3"),
    ])
    music_cost_usd = 0.0

    # Exactly the Remotion component's props — no tool-routing keys (those go
    # in `edit_decisions` below, passed separately to video_compose). Doubles
    # as the artifact record and the file bespoke.props_path points at.
    props = {
        "fps": 30, "width": 1920, "height": 1080,
        "themeConfig": THEME,
        "cuts": cuts,
        "captions": words,
        "audio": {
            "narration": {"src": f"ohmsville/{lesson}/narration/full.mp3"},
            "music": {"src": f"ohmsville/{lesson}/music.mp3", "volume": 0.08,
                      "fade_in_seconds": 1.5, "fade_out_seconds": 3.0},
        },
        "endCard": {"url": shotlist["lessonUrl"], "seconds": 6},
    }
    (art / "composition.json").write_text(json.dumps(props, indent=2))
    (art / "captions.json").write_text(json.dumps(words, indent=2))

    render = PROJECT / "renders" / lesson
    render.mkdir(parents=True, exist_ok=True)
    result = registry.get("video_compose").execute({
        "operation": "render",
        "edit_decisions": {
            "render_runtime": "remotion",
            "composition_mode": "atelier",
            "bespoke": {
                # The shared Remotion entry (registers every composition in
                # Root.tsx, OhmsvilleLesson included) — atelier mode requires
                # this to already live under remotion-composer/ so the bundler
                # can resolve node_modules; it does, so no project-local
                # entry/auto-staged symlink is needed.
                "entry": str(ROOT / "remotion-composer" / "src" / "index.tsx"),
                "composition_id": "OhmsvilleLesson",
                # Atelier mode's ONLY channel for real Remotion props — with no
                # props_path, Remotion silently falls back to Root.tsx's
                # defaultProps (empty cuts/captions/audio) and still reports
                # success.
                "props_path": str(art / "composition.json"),
                "art_direction": ART_DIRECTION,
            },
        },
        "output_path": str(render / "final.mp4"),
    })
    (art / "render_report.json").write_text(json.dumps(
        {"success": result.success, "data": result.data, "error": result.error,
         "cost_usd": result.cost_usd, "duration_seconds": result.duration_seconds},
        indent=2,
    ))
    if not result.success:
        raise RuntimeError(f"video_compose render failed: {result.error}")
    print(f"{lesson}: {render / 'final.mp4'}  music_cost={music_cost_usd}  narration={round(total_seconds, 1)}s")


if __name__ == "__main__":
    main(sys.argv[1])
