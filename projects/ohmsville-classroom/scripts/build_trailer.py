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

# The Spooky Shack's own identity (fix round 4), not build_lesson.py's Science Fair '78 THEME —
# matched verbatim to client/src/home/Home.svelte's `.spookycard` (Seth: "that card turned out
# really, really good... match it rather than inventing a treatment"). surfaceColor is unused by
# anything this trailer renders (no schematic cards) but the interface requires a value.
SPOOKY_THEME = {
    "primaryColor": "#5a3a6a", "accentColor": "#ffb347", "backgroundColor": "#140c1c",
    "surfaceColor": "#140c1c", "textColor": "#f6efdc", "mutedTextColor": "#c9b8a0",
    "headingFont": "Oswald", "bodyFont": "Georgia, 'Times New Roman', serif",
    "captionHighlightColor": "#ffb347", "captionBackgroundColor": "rgba(20,12,28,0.9)",
    "scrimColor": "20,12,28",
    "captionFont": "Georgia, 'Times New Roman', serif",
    # Set below, per trailer_id, once the staged asset path is known (LOGO_DIR/BOARD_BADGE) — see
    # main()'s SPOOKY_THEME.update() call.
}

# Six transparent PNGs cut from Seth's Canva deck, copied once into this project's own assets
# (fix round 4: "copy the files into the OpenMontage project's assets rather than reading them from
# the reference folder at render time") — permanent, like SPOOKY_SHACK_MUSIC above.
#
# Rounds 4-7's props-on-board-beats history: a top corner sat on the busiest row (4); a fixed-small
# bottom-anchored box dodged that only by shrinking near to invisibility (5); scaling the board down
# to leave a guaranteed-empty margin fixed sizing but made the circuit a small rectangle with a
# zombie hand the biggest thing on screen (6); round 7 removed the props from the board beats
# entirely. Seth's correction, round 8: he asked for them to be MOVED, not removed — put them back,
# board full-bleed (round 7's real fix, kept), one prop per board beat living in that beat's own
# genuinely empty dark corner. PROP_FOR's `corner` and `height_frac` are chosen per beat by looking
# at that beat's actual recorded frame (see the fix round 8 report for what was checked), not a
# formula, and not a measuring script — Seth was explicit that scaffolding for a numeric floor/
# ceiling misses the point when "clearly visible, not over a part" is a visual judgement.
#
# Mid-round-8 correction, direct from Seth: the first pass (14-18% visible, must clear every part)
# undershot — he wants the prop clearly present, not hiding in a gap. Revised brief: whole prop
# in frame (not cropped to a sliver), ~20-28% of frame height, overlapping the board/wires/parts is
# fine. The only things a prop must still clear are the caption text and whichever single part the
# narration is naming in that beat's sentence. s3's mummy was first placed bottom-left, which put it
# right on top of the SECOND "LED red" (springs 56/57) — exactly the part s3's own line names
# ("blinking the opposite way round"). Moved to bottom-right, which is clear board there.
PROPS_DIR = PROJECT / "assets" / "props"
# height_frac 0.24 -> CornerProp renders at exactly 24% of frame height (CSS height is fixed, not
# derived from the source art), comfortably inside Seth's 20-28% band for all four props.
PROP_FOR = {
    "s2": ("jack-o-lantern.png", "bottom-right", 0.24, 0.3),
    "s3": ("mummy.png", "bottom-right", 0.24, 0.3),
    "s4": ("zombie-hand.png", "bottom-right", 0.24, 0.3),
    "s5": ("ghost.png", "bottom-left", 0.24, 0.3),
}
# The trailer's own title card (fix round 4), carved out of s1's front: the same witch-hat.png the
# lead's original prop pairing named for "the title", now as the card's own art rather than a
# corner accent over the real footage — real /halloween footage (the hero art fix, round 2) still
# follows immediately after, unchanged.
TITLE_CARD_SECONDS = 2.5
TITLE_CARD_ART = "props/witch-hat.png"
TITLE_CARD_KICKER = "SEVEN HALLOWEEN CIRCUITS · THE OCTOBER MISSION"
TITLE_CARD_TITLE = "Spooky Shack"
# The end card's own art: the site's real halloween/card.jpg (Home.svelte's own spookycard image),
# staged fresh from the Ohmsville repo each render rather than duplicated as a permanent asset here
# — it's the live site's asset, not a one-off from the reference folder.
END_CARD_ART = "card.jpg"

# The brand mark on the board beats (fix round 7, Seth: this is footage headed to YouTube and other
# feeds — a broadcaster's bug). client/public/logo/mono.svg is the site's own single-colour
# wordmark, but it bakes its ink as literal fill/stroke attributes rather than `currentColor`, so a
# plain <img> can't be retinted by CSS — recolored once to the paper cream the lead named and saved
# here permanently, same convention as PROPS_DIR/SPOOKY_SHACK_MUSIC. The site's own
# horizontal-paper.svg/horizontal-red.svg were ruled out explicitly: their baked background
# rectangle would show. See the asset file's own header comment for exactly what changed.
LOGO_DIR = PROJECT / "assets" / "logo"
BOARD_BADGE = "ohmsville-mono-cream.svg"
# Checked against real recorded frames (all four board beats open on the standard board, so one
# choice covers every recipe): the top row's springs and labels run edge to edge with no gap large
# enough for a top-left or top-center mark to clear — see the fix round 7 report for the frames
# looked at. Bottom-left, the lead's own named fallback.
BOARD_BADGE_POSITION = "bottom-left"


def stage(trailer_id: str) -> Path:
    out = PUBLIC / trailer_id
    if out.exists():
        shutil.rmtree(out)
    (out / "narration").mkdir(parents=True)
    (out / "shots").mkdir()
    (out / "props").mkdir()
    (out / "logo").mkdir()
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

    # Stage the title card's prop, the four board-beat props, the board badge (all permanent
    # assets), and the end card's art (fresh from the live site each render — see END_CARD_ART's
    # own comment).
    shutil.copy(PROPS_DIR / "witch-hat.png", out / "props" / "witch-hat.png")
    for filename, _corner, _height_frac, _opacity in PROP_FOR.values():
        shutil.copy(PROPS_DIR / filename, out / "props" / filename)
    shutil.copy(LOGO_DIR / BOARD_BADGE, out / "logo" / BOARD_BADGE)
    card_jpg = OHMSVILLE / "client" / "public" / "halloween" / "card.jpg"
    if not card_jpg.is_file():
        raise RuntimeError(f"end card art missing at {card_jpg}")
    shutil.copy(card_jpg, out / END_CARD_ART)

    cuts, words = [], []
    sections = shotlist["sections"]
    t = 0.0
    for i, s in enumerate(sections):
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
            source_start = s["shot"]["trimStartSeconds"]
            video_start = start
            # The trailer's title card (fix round 4): the first TITLE_CARD_SECONDS of s1's own
            # beat is a graphic card instead of the real /halloween footage, which then plays for
            # the remainder of s1's narration exactly as before (round 2's hero-art fix untouched)
            # — advance the video's own source start by the same amount so it doesn't freeze-frame
            # repeating the instant the card hands off.
            if i == 0 and end - start > TITLE_CARD_SECONDS:
                cuts.append({
                    "id": f"{s['id']}-title", "type": "title", "layer": 0,
                    "in_seconds": round(start, 2), "out_seconds": round(start + TITLE_CARD_SECONDS, 2),
                    "title": TITLE_CARD_TITLE, "kicker": TITLE_CARD_KICKER,
                    "art": f"ohmsville-trailers/{trailer_id}/{TITLE_CARD_ART}",
                })
                video_start = start + TITLE_CARD_SECONDS
                source_start += TITLE_CARD_SECONDS
            prop, prop_corner, prop_height_frac, prop_opacity = PROP_FOR.get(s["id"], (None, None, None, None))
            cuts.append({
                "id": s["id"], "type": "video", "layer": 0,
                "src": f"ohmsville-trailers/{trailer_id}/shots/{s['shot']['file']}",
                "in_seconds": round(video_start, 2), "out_seconds": round(end, 2),
                "sourceStartSeconds": source_start,
                "label": None,  # no lower-third: a trailer names nothing the narration hasn't already said
                **({
                    "prop": f"ohmsville-trailers/{trailer_id}/props/{prop}",
                    "propCorner": prop_corner, "propHeightFrac": prop_height_frac, "propOpacity": prop_opacity,
                } if prop else {}),
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

    # The board badge's position is a per-recipe judgement call (where the top row actually has
    # room), made by looking at real recorded frames, not guessed from CSS — see BOARD_BADGE_POSITION's
    # own comment for what was checked and why.
    theme = {**SPOOKY_THEME, "boardBadge": f"ohmsville-trailers/{trailer_id}/logo/{BOARD_BADGE}",
             "boardBadgePosition": BOARD_BADGE_POSITION}

    props = {
        "fps": 30, "width": 1920, "height": 1080,
        "themeConfig": theme,
        "cuts": cuts,
        "captions": words,
        "audio": {
            "narration": {"src": f"ohmsville-trailers/{trailer_id}/narration/full.mp3"},
            "music": {"src": f"ohmsville-trailers/{trailer_id}/music.mp3", "volume": 0.1,
                      "fade_in_seconds": 1.5, "fade_out_seconds": 3.0},
        },
        # "no lesson end-card" (issue #72): ohmsville.com, not a classroom anchor. Dressed the same
        # way the title card is (fix round 4): the site's own card.jpg behind the scrim.
        "endCard": {
            "url": SITE, "seconds": end_card_seconds,
            "title": "Spooky Shack", "kicker": "THE OCTOBER MISSION",
            "art": f"ohmsville-trailers/{trailer_id}/{END_CARD_ART}",
        },
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
