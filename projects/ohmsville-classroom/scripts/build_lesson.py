#!/usr/bin/env python3
"""Build one Ohmsville classroom lesson video from the Ohmsville repo's shot list.

    python projects/ohmsville-classroom/scripts/build_lesson.py what-electricity-is

The Ohmsville repo owns the script, the narration and the footage; this owns the cut and the render.
Assets are copied under remotion-composer/public/ because Remotion's <Audio> rejects file:// URLs and
the space in "Local Sites" makes absolute URIs fragile (neural-networks-learn hit exactly this).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
# The classroom-video-series work lives on the Ohmsville repo's "classroom-videos"
# worktree, checked out at circuit-city-video (the repo itself is still named
# circuit-city on GitHub) — NOT a sibling "circuit-city" checkout.
OHMSVILLE = Path.home() / "projects" / "circuit-city-video"
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


def stage(lesson: str, shots: Path) -> Path:
    out = PUBLIC / lesson
    if out.exists():
        shutil.rmtree(out)
    (out / "narration").mkdir(parents=True)
    (out / "shots").mkdir()
    (out / "cards").mkdir()
    return out


def captions(section, audio_path, registry):
    """Words from our script, timing from ASR. Never the other way round (commit 6f8317bb).

    align_words_to_reference() takes/returns (word, start, end) TUPLES, not dicts —
    see tools/subtitle/caption_align.py and its real callers (build_launch.py,
    build_hero.py, build_short.py). transcriber.execute() input is `input_path`
    (not `audio_path`), and its word timings come back at
    result.data["word_timestamps"], each a dict — converted to tuples here for
    align_words_to_reference, then back to the caption dict shape on the way out.
    """
    result = registry.get("transcriber").execute({"input_path": str(audio_path)})
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
    out = stage(lesson, shots)

    cuts, narration_segments, words, t = [], [], [], 0.0
    for s in shotlist["sections"]:
        audio = out / "narration" / f"{s['id']}.mp3"
        shutil.copy(s["audio"], audio)
        dur = round(s["audioSeconds"] + 0.4, 2)
        narration_segments.append({"asset_id": s["id"], "start_seconds": round(t, 2)})
        for w in captions(s, audio, registry):
            words.append({"word": w["word"], "startMs": int(t * 1000) + w["startMs"], "endMs": int(t * 1000) + w["endMs"]})

        if s["shot"]:
            shutil.copy(shots / s["shot"]["file"], out / "shots" / s["shot"]["file"])
            cuts.append({
                "id": s["id"], "type": "video", "layer": 0,
                "src": f"ohmsville/{lesson}/shots/{s['shot']['file']}",
                "in_seconds": round(t, 2), "out_seconds": round(t + dur, 2),
                "sourceStartSeconds": s["shot"]["trimStartSeconds"],
                "label": s["label"],
            })
        elif s["card"]["kind"] == "schematic":
            shutil.copy(shots / s["card"]["file"], out / "cards" / s["card"]["file"])
            cuts.append({"id": s["id"], "type": "card", "layer": 0,
                         "src": f"ohmsville/{lesson}/cards/{s['card']['file']}",
                         "in_seconds": round(t, 2), "out_seconds": round(t + dur, 2), "label": s["label"]})
        else:
            cuts.append({"id": s["id"], "type": s["card"]["kind"], "layer": 0,
                         "in_seconds": round(t, 2), "out_seconds": round(t + dur, 2),
                         "title": shotlist["title"], "subtitle": "Intro to Electronics · Ohmsville",
                         "url": shotlist["lessonUrl"], "label": s["label"]})
        t += dur

    # one narration bed, concatenated in order; music underneath, ducked
    concat = out / "narration" / "full.mp3"
    listfile = out / "narration" / "list.txt"
    listfile.write_text("".join(f"file '{out / 'narration' / (s['id'] + '.mp3')}'\n" for s in shotlist["sections"]))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(concat)], check=True, capture_output=True)

    music_result = registry.get("pixabay_music").execute({
        "query": "calm workshop instrumental", "min_duration": int(t), "max_duration": int(t) + 90,
        "output_path": str(out / "music.mp3"),
    })
    if not music_result.success:
        raise RuntimeError(f"pixabay_music failed: {music_result.error}")

    composition = {
        "render_runtime": "remotion",
        "composition_mode": "atelier",
        "bespoke": {
            # The shared Remotion entry (registers every composition in Root.tsx,
            # OhmsvilleLesson included) — atelier mode requires this to already
            # live under remotion-composer/ so the bundler can resolve node_modules;
            # it does, so no project-local entry/auto-staged symlink is needed.
            "entry": str(ROOT / "remotion-composer" / "src" / "index.tsx"),
            "composition_id": "OhmsvilleLesson",
        },
        "fps": 30, "width": 1920, "height": 1080,
        "themeConfig": THEME,
        "intro": "ohmsville/intro.mp4",
        "cuts": cuts,
        "captions": words,
        "audio": {
            "narration": {"src": f"ohmsville/{lesson}/narration/full.mp3"},
            "music": {"src": f"ohmsville/{lesson}/music.mp3", "volume": 0.08,
                      "fade_in_seconds": 1.5, "fade_out_seconds": 3.0,
                      "ducking": {"enabled": True, "reduction_db": -8}},
        },
        "endCard": {"url": shotlist["lessonUrl"], "seconds": 6},
    }
    art = PROJECT / "artifacts" / lesson
    art.mkdir(parents=True, exist_ok=True)
    (art / "composition.json").write_text(json.dumps(composition, indent=2))
    (art / "captions.json").write_text(json.dumps(words, indent=2))

    render = PROJECT / "renders" / lesson
    render.mkdir(parents=True, exist_ok=True)
    result = registry.get("video_compose").execute({
        "operation": "render",
        "edit_decisions": composition,
        "output_path": str(render / "final.mp4"),
        "remotion_timeout_ms": 900_000,
    })
    (art / "render_report.json").write_text(json.dumps(
        {"success": result.success, "data": result.data, "error": result.error,
         "cost_usd": result.cost_usd, "duration_seconds": result.duration_seconds},
        indent=2,
    ))
    if not result.success:
        raise RuntimeError(f"video_compose render failed: {result.error}")
    print(f"{lesson}: {render / 'final.mp4'}  music_cost={music_result.cost_usd}  narration={round(t, 1)}s")


if __name__ == "__main__":
    main(sys.argv[1])
