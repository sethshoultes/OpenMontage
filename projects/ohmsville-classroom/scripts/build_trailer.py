#!/usr/bin/env python3
"""Build an Ohmsville trailer video from the Ohmsville repo's trailer shot list.

    python projects/ohmsville-classroom/scripts/build_trailer.py spooky-shack
    OHMSVILLE_REPO=~/projects/circuit-city-trailer python projects/ohmsville-classroom/scripts/build_trailer.py spooky-shack

Sibling to build_lesson.py (issue #72 in the Ohmsville repo), sharing its snapshot/caption/ffmpeg
helpers rather than forking them. What differs from a lesson:

  - the shots live under client/.shots/trailers/<id>/, not client/.shots/<lesson>/;
  - there is no schematic card and no per-lesson chapters/description — a trailer is title shot,
    a handful of real shots, a mission shot, then a closing card;
  - the closing card points at ohmsville.com, not a lesson's classroom anchor — "no lesson
    end-card" (issue #72) means exactly this: OhmsvilleLesson.tsx's own EndPlate is reused
    unchanged, only its `url`/`title` props differ;
  - the music bed is the trailer's own (SPOOKY_SHACK_MUSIC below), not the shared lesson-series
    bed — same stream_loop-and-trim technique, because the generated bed (an ElevenLabs
    music_gen result, ~45s) need not already be the trailer's exact runtime.

The Remotion composition itself (OhmsvilleLesson) needed NO changes: its four cut types
(video/card/title/end) and its endCard synthesis are already generic over what produced them.
"card: title" and "kind: end" only ever change which of those four types a section becomes on the
Ohmsville-repo side (client/src/classroom/videoScript.ts) — the composition just renders whichever
type it's handed.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
OHMSVILLE = Path(os.environ.get("OHMSVILLE_REPO", "~/projects/circuit-city-trailer")).expanduser()
PUBLIC = ROOT / "remotion-composer" / "public" / "ohmsville-trailers"
SITE = "https://ohmsville.com"

sys.path.insert(0, str(ROOT))
from tools.tool_registry import registry  # noqa: E402

registry.discover()

# Reuse build_lesson.py's THEME, ART_DIRECTION, SECTION_GAP_SECONDS and helper functions rather
# than duplicating them — same directory, imported as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_lesson as lesson  # noqa: E402

THEME = lesson.THEME
ART_DIRECTION = lesson.ART_DIRECTION
SECTION_GAP_SECONDS = lesson.SECTION_GAP_SECONDS
run_ffmpeg = lesson.run_ffmpeg
ffprobe_duration = lesson.ffprobe_duration
captions_for = lesson.captions

# The trailer's own bed (issue #72: "its own bed, not the series bed: something slow and minor"),
# generated once via ElevenLabs music_gen and saved here as a permanent per-trailer asset,
# following SERIES_MUSIC's own convention (build_lesson.py) of a committed, reusable track rather
# than a per-render generation.
SPOOKY_SHACK_MUSIC = PROJECT / "assets" / "music" / "spooky_shack_bed.mp3"


def stage(trailer_id: str) -> Path:
    out = PUBLIC / trailer_id
    if out.exists():
        shutil.rmtree(out)
    (out / "narration").mkdir(parents=True)
    (out / "shots").mkdir()
    return out


def main(trailer_id: str) -> None:
    art = PROJECT / "artifacts" / f"trailer-{trailer_id}"
    transcript_dir = art / "transcripts"
    art.mkdir(parents=True, exist_ok=True)

    # Same snapshot-then-validate dance as build_lesson.py's main(), for the same reason: the
    # recorder writes shotlist.json last, so a naive copytree can silently miss it mid-write.
    live_shots = OHMSVILLE / "client" / ".shots" / "trailers" / trailer_id
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
    out = stage(trailer_id)

    cuts, words = [], []
    sections = shotlist["sections"]
    t = 0.0
    for s in sections:
        audio = out / "narration" / f"{s['id']}.mp3"
        shutil.copy(s["audio"], audio)

        # Same timeline-from-measured-audio fix as build_lesson.py: derive start/end from THIS
        # clip's own ffprobe duration, never shotlist.json's upstream-computed seconds.
        real_dur = ffprobe_duration(audio)
        start = t
        end = start + real_dur
        t = end + SECTION_GAP_SECONDS
        for w in captions_for(s, audio, transcript_dir):
            words.append({"word": w["word"], "startMs": int(start * 1000) + w["startMs"],
                          "endMs": int(start * 1000) + w["endMs"], "liftPx": 0})

        if s["shot"]:
            shutil.copy(shots / s["shot"]["file"], out / "shots" / s["shot"]["file"])
            cuts.append({
                "id": s["id"], "type": "video", "layer": 0,
                "src": f"ohmsville-trailers/{trailer_id}/shots/{s['shot']['file']}",
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "sourceStartSeconds": s["shot"]["trimStartSeconds"],
                "label": None,  # no lower-third: a trailer names nothing the narration hasn't already said
            })
        elif s["card"]["kind"] == "end" and cuts:
            # The trailer's closing section (kind: end, shot: none) has no footage of its own —
            # its narration is the voiceover for the closing card, so the last real shot holds
            # through it (same fix as build_lesson.py's own end-card handling), and
            # OhmsvilleLesson.tsx's endCard synthesis adds the actual plate afterward, silent.
            cuts[-1]["out_seconds"] = round(end, 2)
        else:
            # First-section edge case only (a "kind: end" section with no prior cut to hold on) —
            # a trailer never authors card: title/schematic/none itself (videoScript.ts derives
            # card from kind/position), so this path is defensive, not exercised by Spooky Shack.
            cuts.append({"id": s["id"], "type": s["card"]["kind"], "layer": 0,
                         "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                         "title": shotlist["title"], "label": None})

    # One narration bed, built the same decode-and-re-encode way as build_lesson.py (never the
    # concat demuxer's -c copy, which reintroduces per-splice drift — see that script's comment).
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

    full_duration = ffprobe_duration(concat)
    if abs(full_duration - t) > 0.15:
        raise RuntimeError(
            f"narration bed duration {full_duration:.3f}s does not match "
            f"this script's own computed timeline total {t:.3f}s — the concat "
            f"construction has a bug, cut/caption placement would be wrong "
            f"against the actual audio"
        )

    total_seconds = max(c["out_seconds"] for c in cuts) if cuts else 0.0
    end_card_seconds = 6.0

    # Music: the trailer's own bed (SPOOKY_SHACK_MUSIC), not the lesson series' — issue #72 is
    # explicit that a trailer wants "something slow and minor", not the workshop's own identity
    # track. Generated once (ElevenLabs music_gen, ~45s, $0.075) and looped/trimmed to the
    # trailer's real runtime, same technique as build_lesson.py's SERIES_MUSIC handling.
    if not SPOOKY_SHACK_MUSIC.exists():
        raise RuntimeError(
            f"trailer music bed missing at {SPOOKY_SHACK_MUSIC} — generate it once with "
            f"music_gen (see the fix report for the prompt) and save it there before rendering"
        )
    render_seconds = total_seconds + end_card_seconds
    run_ffmpeg([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(SPOOKY_SHACK_MUSIC),
        "-t", f"{render_seconds:.3f}", "-c:a", "libmp3lame", "-q:a", "4",
        str(out / "music.mp3"),
    ])

    props = {
        "fps": 30, "width": 1920, "height": 1080,
        "themeConfig": THEME,
        "cuts": cuts,
        "captions": words,
        "audio": {
            "narration": {"src": f"ohmsville-trailers/{trailer_id}/narration/full.mp3"},
            "music": {"src": f"ohmsville-trailers/{trailer_id}/music.mp3", "volume": 0.1,
                      "fade_in_seconds": 1.5, "fade_out_seconds": 3.0},
        },
        # "no lesson end-card" (issue #72): ohmsville.com, not a classroom anchor.
        "endCard": {"url": SITE, "seconds": end_card_seconds},
    }
    (art / "composition.json").write_text(json.dumps(props, indent=2))
    (art / "captions.json").write_text(json.dumps(words, indent=2))

    render = PROJECT / "renders" / trailer_id
    render.mkdir(parents=True, exist_ok=True)
    result = registry.get("video_compose").execute({
        "operation": "render",
        "edit_decisions": {
            "render_runtime": "remotion",
            "composition_mode": "atelier",
            "bespoke": {
                "entry": str(ROOT / "remotion-composer" / "src" / "index.tsx"),
                "composition_id": "OhmsvilleLesson",
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
    print(f"{trailer_id}: {render / 'final.mp4'}  narration={round(total_seconds, 1)}s  "
          f"total={round(render_seconds, 1)}s")


if __name__ == "__main__":
    main(sys.argv[1])
