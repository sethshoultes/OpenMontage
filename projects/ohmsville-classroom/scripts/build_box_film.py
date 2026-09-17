#!/usr/bin/env python3
"""Build "The Box" from the Ohmsville repo's trailer shot list.

    OHMSVILLE_REPO=~/.herdr/worktrees/circuit-city/box-film \
      .venv/bin/python projects/ohmsville-classroom/scripts/build_box_film.py

Third sibling to build_lesson.py and build_trailer.py, sharing their helpers rather than forking
them. It exists as its own script because The Box is not the Spooky Shack's shape:

  - the Spooky Shack opens on real /halloween footage with a graphic title card carved out of its
    front, and dresses each board beat with a Halloween prop. This film has no props at all —
    its question is "what does it feel like to be handed something with no instructions?"
    (docs/video-guidelines.md), and a decorative cut-out over the board answers no part of it;
  - its first and last beats carry no footage (`shot: none` in content/trailers/box-film.md).
    The kit box opening IS the first beat, animated in the compositor because Seth ruled the
    KitBox component's own lid CSS stays untouched — see remotion-composer/src/components/KitBox.tsx;
  - the closing beat is a real `end`-typed cut rather than a hold on the previous shot, so the
    film ends on the box rather than on a page of classroom prose.

Everything else — the snapshot, the measured-audio timeline, the caption alignment, the
narration concat, the gap bridging, the music loop — is the same code path as the Spooky Shack.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
PUBLIC = ROOT / "remotion-composer" / "public" / "ohmsville-trailers"
SITE = "https://ohmsville.com"
TRAILER_ID = "box-film"

sys.path.insert(0, str(ROOT))
from tools.tool_registry import registry  # noqa: E402

registry.discover()

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_lesson as lesson  # noqa: E402
import build_trailer as trailer  # noqa: E402

ART_DIRECTION = lesson.ART_DIRECTION
SECTION_GAP_SECONDS = lesson.SECTION_GAP_SECONDS
run_ffmpeg = lesson.run_ffmpeg
ffprobe_duration = lesson.ffprobe_duration
captions_for = lesson.captions

# This film's own bed, generated once via ElevenLabs music_gen (75s, $0.125) and kept here as a
# permanent asset, the same convention as SERIES_MUSIC and SPOOKY_SHACK_MUSIC. video-guidelines.md
# says one bed per family and a new one only when the family is new: the series bed is the
# classroom's workshop track, written to sit under instruction, and the Spooky Shack's is slow and
# minor. This is neither — it is a memory of a kit on a bedroom floor, so it is its own family of
# one until a second film of this kind needs it. Prompt: slow Rhodes and pad, faint tape hiss,
# no drums, nostalgic rather than sad.
BOX_MUSIC = PROJECT / "assets" / "music" / "box_film_bed.mp3"

# Science Fair '78 — build_lesson.py's own THEME, not a new one. The Spooky Shack needed its own
# palette because the pack has its own identity on the home page; this film is about the kit
# itself, so the kit's house colours ARE its colours. Two additions on top: `scrimColor`, so the
# title and end cards can push the box behind the same gradient Home.svelte uses; and
# `boardBadge`, the quiet wordmark the guidelines ask for on board beats.
BOX_THEME = {
    **lesson.THEME,
    "scrimColor": "36,28,16",  # backgroundColor #241c10
}

# The same recoloured wordmark the Spooky Shack uses (see build_trailer.py's LOGO_DIR comment for
# why the site's own mono.svg cannot simply be retinted by CSS).
LOGO_DIR = PROJECT / "assets" / "logo"
BOARD_BADGE = trailer.BOARD_BADGE
# Every board beat in this film records the standard board on the default sf78 skin, whose top row
# of springs and labels runs edge to edge — checked on the real recorded frames of s2-s5, which all
# share one framing. Bottom-left is the corner with room.
BOARD_BADGE_POSITION = "bottom-left"

# The box on the title card opens a beat into the narration ("Somebody handed you a flat box..."),
# not on the first frame: the shot is a closed box first, so that there is something to open.
TITLE_BOX = {"open": "animate", "openStartSeconds": 1.2, "widthFrac": 0.46, "centerXFrac": 0.68, "centerYFrac": 0.54}
# On the end card it is already open and stays that way — the offer is the thing lying in it.
END_BOX = {"open": "open", "widthFrac": 0.42, "centerXFrac": 0.71, "centerYFrac": 0.55}
TITLE_KICKER = "OHMSVILLE"
END_KICKER = "NOTHING TO INSTALL · NOTHING TO BUY"
END_TITLE = "Open the box"
# How long the end card holds after the last word, so the URL is readable. The guidelines' rule is
# that the end card holds after the voice and never over it; here the card is already on screen
# under the closing narration, so this is the silent tail only.
END_HOLD_SECONDS = 3.0


def main() -> None:
    art = PROJECT / "artifacts" / f"trailer-{TRAILER_ID}"
    transcript_dir = art / "transcripts"
    art.mkdir(parents=True, exist_ok=True)

    shots = art / "_source_snapshot"
    shotlist = trailer.snapshot(TRAILER_ID, shots)
    out = trailer.stage(TRAILER_ID)
    shutil.copy(LOGO_DIR / BOARD_BADGE, out / "logo" / BOARD_BADGE)

    if not BOX_MUSIC.exists():
        raise RuntimeError(f"music bed missing at {BOX_MUSIC} — generate it once with music_gen")

    cuts, words = [], []
    sections = shotlist["sections"]
    t = 0.0
    for s in sections:
        audio = out / "narration" / f"{s['id']}.mp3"
        shutil.copy(s["audio"], audio)

        # Same timeline-from-measured-audio rule as both siblings: this clip's own ffprobe
        # duration, never shotlist.json's upstream-computed seconds.
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
                "src": f"ohmsville-trailers/{TRAILER_ID}/shots/{s['shot']['file']}",
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "sourceStartSeconds": s["shot"]["trimStartSeconds"],
                "label": None,  # no lower-third: a trailer names nothing the narration hasn't said
            })
        elif s["card"]["kind"] == "title":
            cuts.append({
                "id": s["id"], "type": "title", "layer": 0,
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "title": shotlist["title"], "kicker": TITLE_KICKER, "box": TITLE_BOX, "label": None,
            })
        elif s["card"]["kind"] == "end":
            # A real end cut, not a hold on the previous shot (build_trailer.py's own choice for the
            # Spooky Shack). The closing line here is the offer — "no account, nothing to install,
            # nothing to buy" — and the picture it belongs over is the open box, not the tail of a
            # classroom page. Emitting it as type "end" also tells OhmsvilleLesson.tsx not to
            # synthesize a second, duplicate plate afterwards (its own hasEndCut check).
            cuts.append({
                "id": s["id"], "type": "end", "layer": 0,
                "in_seconds": round(start, 2), "out_seconds": round(end + END_HOLD_SECONDS, 2),
                "url": SITE, "title": END_TITLE, "kicker": END_KICKER, "box": END_BOX, "label": None,
            })
        else:
            raise RuntimeError(f"{s['id']}: no shot and card kind {s['card']['kind']!r} — nothing to render")

    # Bridge the SECTION_GAP_SECONDS breath between beats: `t` advances by that gap after every
    # section but nothing fills the picture for it, so without this every cut-to-cut boundary is a
    # real hole with the plain theme background showing through — which looks exactly like a
    # dropped shot. Every cut holds its last frame until the next one begins; the final cut is
    # never extended, so the runtime is unchanged. (build_trailer.py hit this on all five of the
    # Spooky Shack's boundaries.)
    for i in range(len(cuts) - 1):
        if cuts[i]["out_seconds"] < cuts[i + 1]["in_seconds"]:
            cuts[i]["out_seconds"] = cuts[i + 1]["in_seconds"]

    # One narration bed, decoded and re-encoded (never the concat demuxer's -c copy, which
    # reintroduces per-splice drift — see build_lesson.py's comment).
    silence = art / "_silence.mp3"
    run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(SECTION_GAP_SECONDS), "-c:a", "libmp3lame", "-q:a", "6", str(silence)])
    concat = out / "narration" / "full.mp3"
    inputs = []
    for s in sections:
        inputs += ["-i", str(out / "narration" / f"{s['id']}.mp3"), "-i", str(silence)]
    n = len(sections) * 2
    filter_graph = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    run_ffmpeg(["ffmpeg", "-y", *inputs, "-filter_complex", filter_graph, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "4", str(concat)])

    full_duration = ffprobe_duration(concat)
    if abs(full_duration - t) > 0.15:
        raise RuntimeError(
            f"narration bed duration {full_duration:.3f}s does not match this script's own computed "
            f"timeline total {t:.3f}s — cut and caption placement would be wrong against the audio"
        )

    render_seconds = max(c["out_seconds"] for c in cuts)
    run_ffmpeg(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(BOX_MUSIC),
                "-t", f"{render_seconds:.3f}", "-c:a", "libmp3lame", "-q:a", "4", str(out / "music.mp3")])

    theme = {**BOX_THEME, "boardBadge": f"ohmsville-trailers/{TRAILER_ID}/logo/{BOARD_BADGE}",
             "boardBadgePosition": BOARD_BADGE_POSITION}
    props = {
        "fps": 30, "width": 1920, "height": 1080,
        "themeConfig": theme,
        "cuts": cuts,
        "captions": words,
        "audio": {
            "narration": {"src": f"ohmsville-trailers/{TRAILER_ID}/narration/full.mp3"},
            "music": {"src": f"ohmsville-trailers/{TRAILER_ID}/music.mp3", "volume": 0.1,
                      "fade_in_seconds": 1.5, "fade_out_seconds": 3.0},
        },
        # `cuts` already carries a real end cut, so this only supplies the URL the plate falls back
        # to; OhmsvilleLesson.tsx's hasEndCut check keeps it from adding a second plate.
        "endCard": {"url": SITE, "seconds": 0},
    }
    (art / "composition.json").write_text(json.dumps(props, indent=2))
    (art / "captions.json").write_text(json.dumps(words, indent=2))

    render = PROJECT / "renders" / TRAILER_ID
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
         "cost_usd": result.cost_usd, "duration_seconds": result.duration_seconds}, indent=2))
    if not result.success:
        raise RuntimeError(f"video_compose render failed: {result.error}")
    print(f"{TRAILER_ID}: {render / 'final.mp4'}  total={round(render_seconds, 1)}s")


if __name__ == "__main__":
    main()
