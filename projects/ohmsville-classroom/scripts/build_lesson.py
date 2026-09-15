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
import shutil
import subprocess
import sys
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
# record-shots.ts (the Ohmsville repo) advances its own `running.t` by
# `clip.seconds + 0.4` per section — shotlist.json's `startSeconds` assumes a
# 0.4s gap after every clip, including the last. To keep that assumption true
# of the actual audio we render against, the narration bed below inserts real
# 0.4s silence between clips rather than concatenating them gapless — matching
# the upstream repo's math instead of second-guessing it.
SECTION_GAP_SECONDS = 0.4


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
    shots = OHMSVILLE / "client" / ".shots" / lesson
    shotlist = json.loads((shots / "shotlist.json").read_text())
    out = stage(lesson)

    art = PROJECT / "artifacts" / lesson
    transcript_dir = art / "transcripts"
    art.mkdir(parents=True, exist_ok=True)

    cuts, words = [], []
    sections = shotlist["sections"]
    for i, s in enumerate(sections):
        audio = out / "narration" / f"{s['id']}.mp3"
        shutil.copy(s["audio"], audio)

        # Cut boundaries come from the shotlist's OWN startSeconds, not a
        # second, independently recomputed timeline — but startSeconds itself
        # already bakes in a 0.4s gap after every clip (record-shots.ts:
        # `running.t = running.t + clip.seconds + 0.4`). That's only true of
        # the actual narration audio if the bed we build actually has those
        # gaps in it — see the real silence splicing below, not a gapless
        # concat, which is what made an earlier version of this fix a relocation
        # of the same drift rather than a real one.
        start = s["startSeconds"]
        end = sections[i + 1]["startSeconds"] if i + 1 < len(sections) else start + s["audioSeconds"] + SECTION_GAP_SECONDS
        for w in captions(s, audio, transcript_dir):
            words.append({"word": w["word"], "startMs": int(start * 1000) + w["startMs"], "endMs": int(start * 1000) + w["endMs"]})

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
        else:
            # Covers the remaining CardKind values (title, end, ...) — including
            # the shotlist's own final "end" section, which is a real end-typed
            # cut, not something OhmsvilleLesson.tsx needs to synthesize.
            cuts.append({"id": s["id"], "type": s["card"]["kind"], "layer": 0,
                         "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                         "title": shotlist["title"], "subtitle": "Intro to Electronics · Ohmsville",
                         "url": shotlist["lessonUrl"], "label": s["label"]})

    # One narration bed: each clip followed by a real SECTION_GAP_SECONDS of
    # silence (including after the last clip, matching record-shots.ts's own
    # running.t, which folds the final +0.4 into totalSeconds too). Built with
    # ffmpeg's `concat` audio FILTER (decode-and-re-encode once), not the
    # concat DEMUXER's `-c copy` — stream-copying several independently
    # LAME-encoded MP3s introduces ~20-50ms of encoder priming/padding at
    # EVERY splice point (verified empirically: 3 clips + 3 gaps came out
    # ~0.19s long against nominal), which silently reintroduces the same
    # class of drift this fix exists to remove. The filter graph decodes
    # every input to PCM and re-encodes the whole bed as one continuous
    # stream, so there's no per-file boundary left to drift at (verified:
    # exact match against nominal duration to the millisecond).
    silence = out / "narration" / "_silence.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", str(SECTION_GAP_SECONDS), "-c:a", "libmp3lame", "-q:a", "6", str(silence)],
        check=True, capture_output=True,
    )
    concat = out / "narration" / "full.mp3"
    inputs = []
    for s in sections:
        inputs += ["-i", str(out / "narration" / f"{s['id']}.mp3"), "-i", str(silence)]
    n = len(sections) * 2
    filter_graph = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", filter_graph, "-map", "[out]",
         "-c:a", "libmp3lame", "-q:a", "4", str(concat)],
        check=True, capture_output=True,
    )

    # Sanity check: the bed we just built should land within ~150ms of the
    # shotlist's own totalSeconds (same running.t this section's
    # startSeconds/gap math is derived from) — the filter_complex concat
    # above measured exact to the millisecond in testing, so anything beyond
    # a small margin means this arithmetic has drifted again.
    full_duration = float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(concat)]
    ).strip())
    expected = shotlist.get("totalSeconds")
    if expected is not None and abs(full_duration - expected) > 0.15:
        raise RuntimeError(
            f"narration bed duration {full_duration:.2f}s does not match "
            f"shotlist totalSeconds {expected:.2f}s — startSeconds/cut timing "
            f"would be wrong against the actual audio"
        )

    total_seconds = max(c["out_seconds"] for c in cuts) if cuts else 0.0
    music_result = registry.get("pixabay_music").execute({
        "query": "calm workshop instrumental", "min_duration": int(total_seconds), "max_duration": int(total_seconds) + 90,
        "output_path": str(out / "music.mp3"),
    })
    if not music_result.success:
        raise RuntimeError(f"pixabay_music failed: {music_result.error}")

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
    print(f"{lesson}: {render / 'final.mp4'}  music_cost={music_result.cost_usd}  narration={round(total_seconds, 1)}s")


if __name__ == "__main__":
    main(sys.argv[1])
