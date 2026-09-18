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
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
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

# The inventor films' own bed (a new family, not the Halloween one — one bed per family, reused;
# see docs/film-pipeline.md's Music section). ElevenLabs music_gen, $0.30, committed at this path.
INVENTORS_MUSIC = PROJECT / "assets" / "music" / "inventors_bed.mp3"

# The inventors family reuses build_lesson.py's own THEME — the site's real brand palette, already
# shown on every lesson film and matched to client/src/site/Inventors.svelte/InventorPage.svelte —
# rather than inventing a bespoke campaign skin the way SPOOKY_THEME is bespoke for the Spooky
# Shack. scrimColor and captionFont are the two fields lesson.THEME doesn't carry (it has no need
# of them outside a trailer); scrimColor is backgroundColor's own RGB triple (#241c10 → 36,28,16,
# already implicit in lesson.THEME's own captionBackgroundColor), and captionFont mirrors
# SPOOKY_THEME's convention of matching bodyFont.
INVENTORS_THEME = {**lesson.THEME, "scrimColor": "36,28,16", "captionFont": lesson.THEME["bodyFont"]}

# The town film's own bed (#92). A third family: a film about the place, not about a person and not
# about the bench, so none of the three existing beds fits — the inventors' sits under a biography,
# the box film's under a box, the Spooky Shack's is slow and minor. One bed per family, reused
# (docs/film-pipeline.md's Music section). ElevenLabs music_gen, 240s, $0.40, committed at this path.
OHMSVILLE_MUSIC = PROJECT / "assets" / "music" / "ohmsville_bed.mp3"

# The town family's palette. Same base as INVENTORS_THEME — the site's real Science Fair '78 brand
# ground, whose gold the town page's own kid skin already shares (client/src/kids/kids.css's
# --kid-yellow is #ffd21f, the fill of the active era tab in every street beat) — with primaryColor
# moved to the town's own accent red (--kid-accent, #c0392b: the ring around the selected building
# and around that era tab). That is the era palette without touching backgroundColor, and
# backgroundColor must not move. check_render.py scores each frame's share of pixels within
# GROUND_TOL (6) of the theme ground, and six of this film's ten beats are a full-frame #4ec3e8
# halftone sky: a ground anywhere near that blue would score every street beat as a bare frame and
# fail a correct film. #241c10 sits ~150 RGB units away on every channel, so the check keeps working.
OHMSVILLE_THEME = {**lesson.THEME, "primaryColor": "#c0392b", "scrimColor": "36,28,16",
                   "captionFont": lesson.THEME["bodyFont"]}

# The interview family's own bed (#92 film 2). `music: profiles` has been in all seven profile
# scripts since #89, but those films were composited by scripts/persona-interview-composite.sh,
# which lays no bed at all, so the name existed and the file never did. Generated once here at the
# documentary's own length (ElevenLabs music_gen, 265s, $0.4417) and committed at this path, which
# also makes the seven profile scripts true if any of them is ever rendered through this pipeline.
# Warmer and quieter than the town bed on purpose: it sits under people talking, not under a
# narrator over pictures.
PROFILES_MUSIC = PROJECT / "assets" / "music" / "profiles_bed.mp3"

# The interview family's palette: the site's own brand ground, exactly as the inventors and the
# town film use it. No campaign skin - the pictures are the town film's own stills and seven
# talking heads on the site's cream, and a bespoke palette would only make one family's beats a
# different colour from the other's for no reason a viewer could name.
PROFILES_THEME = {**lesson.THEME, "scrimColor": "36,28,16", "captionFont": lesson.THEME["bodyFont"]}

# Per-family configuration: everything the boundary comment above PERCEPTO_PROPS calls "the
# family's" (the theme, the title card's own art, the end card's art) now keyed by family instead
# of hardcoded, so a second family (inventors) can exist without a second copy of main(). The board
# badge/position stay OUTSIDE this dict on purpose: they're the site's own brand mark on every
# trailer regardless of family ("a broadcaster's bug" — see BOARD_BADGE_POSITION's own comment),
# not a campaign skin element, so both families use the identical LOGO_DIR/BOARD_BADGE/
# BOARD_BADGE_POSITION constants below unchanged.
FAMILIES = {
    "halloween": {
        "theme": SPOOKY_THEME,
        "title_card_art_file": "witch-hat.png",
        "end_card_source": ("halloween", "card.jpg"),
    },
    "inventors": {
        "theme": INVENTORS_THEME,
        # This path is genuinely live for both current inventor scripts (s1 is `shot: none`, so
        # the title carve in main()'s shot-branch never runs, but the elif "title" branch covers
        # the whole beat with this art instead — see its own comment). It must therefore be a
        # full-bleed-safe image under object-fit: cover on a 16:9 frame, not a corner-prop shape.
        # nib-pen.png (committed at PROPS_DIR alongside the other four tool props, used correctly
        # elsewhere as a narrow CornerProp) is wrong for this role: 221x646, 16%-opaque, cropped to
        # almost nothing under cover. inventors-card.jpg is a copy of the site's own vintage
        # kit-box art (client/src/site/seo.ts's SITE + "/gallery/derived/og-card.jpg", the same
        # file used below as end_card_source) placed in PROPS_DIR — opaque (JPG, no alpha) and
        # 1200x630 (aspect 1.905), close enough to 16:9 (1.778) that cover barely crops it.
        "title_card_art_file": "inventors-card.jpg",
        # The site's own vintage kit-box art (client/src/site/seo.ts's SITE + "/gallery/derived/
        # og-card.jpg"), not a per-film asset — matches the "dressed the same way the title card
        # is: the site's own card.jpg behind the scrim" convention with the inventors' own site
        # image standing in for Halloween's card.jpg.
        "end_card_source": ("gallery", "derived", "og-card.jpg"),
    },
    "profiles": {
        "theme": PROFILES_THEME,
        # The ART is genuinely unused by the documentary, and named anyway for interface parity:
        # its s1 is `shot: none` with its own `art:`, so main()'s title branch takes the beat's own
        # illustration (classroom-desks.png, the teller's room) in place of the family's plate -
        # the same path Volta and Ohm take. If a second film in this family ever opens without art
        # of its own, this is what it gets. The title card's TEXT is used either way.
        "title_card_art_file": "inventors-card.jpg",
        # The site's own vintage kit-box art, as for the inventors and the town: the closing line
        # is "These are made-up people in a made-up town. The kit is real," and this is the kit.
        "end_card_source": ("gallery", "derived", "og-card.jpg"),
    },
    "ohmsville": {
        "theme": OHMSVILLE_THEME,
        # Its own title-card art, per the inventors' fix 2 ("if you add an eleventh family, give it
        # its own title-card art file rather than reusing a prop's"). This one is a real frame of
        # the 1978 street, pulled from s1's own recording: the town film's title card is the town.
        # Opaque JPG at the delivered 1920x1080, so `cover` neither crops nor letterboxes it.
        # s1 has a shot, so this art is used for the carved TITLE_CARD_SECONDS at the film's front
        # (the Percepto path), not for a whole shot-less beat (the Volta/Ohm path).
        "title_card_art_file": "ohmsville-card-counter.jpg",
        # The site's own vintage kit-box art, same as the inventors family: the closing line is
        # "Ohmsville is a made-up town. The kit is real," and this is the kit.
        "end_card_source": ("gallery", "derived", "og-card.jpg"),
    },
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
#
# opacity/brightness/saturate is per-prop, not a shared constant: the mummy, jack-o-lantern and
# zombie-hand are dense, saturated art that still reads as atmosphere at the original 0.3/0.5/0.65
# darkening. The ghost is pale, low-saturation art (a white body, thin dark outline, no solid fill
# to hold onto — see assets/props/ghost.png) that the same treatment washes out to almost nothing
# against the near-black board (checked against a real extracted frame — it read as a dark smudge,
# not a ghost). Raised for that one prop only, checked the same way (a CSS-filter simulation
# composited over the board's own near-black, then confirmed on a real rendered frame): 0.85/0.85
# brightness/saturate and 0.45 opacity reads clearly as a ghost at a glance, at roughly the mummy's
# own visibility, still dimmer than full brightness — "mostly visible, legible beats subtle"
# (video-guidelines.md), not a return to full opacity.
PROP_FOR = {
    "s2": ("jack-o-lantern.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s3": ("mummy.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s4": ("zombie-hand.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s5": ("ghost.png", "bottom-left", 0.24, 0.45, 0.85, 0.85),
}
# The trailer's own title card (fix round 4), carved out of s1's front: the same witch-hat.png the
# lead's original prop pairing named for "the title", now as the card's own art rather than a
# corner accent over the real footage — real /halloween footage (the hero art fix, round 2) still
# follows immediately after, unchanged.
TITLE_CARD_SECONDS = 2.5
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

# Percepto (content/trailers/percepto.md) is the Spooky Shack's shape exactly — real /halloween
# footage with a title card carved out of its front, board beats, the campaign page, then a closing
# `kind: end` section that the last shot holds through. Same pack, same skin, same theme, and
# `music: spooky` in its own frontmatter, which is the same bed: video-guidelines.md's "one bed per
# family, reused" and this is that family. So it is a second row in this script rather than a third
# sibling script — build_box_film.py exists because The Box is a genuinely different shape (no
# props, two beats with no footage, a real end cut), which is not true here.
#
# Props (the four proven ones; see PROP_FOR's history above for why each carries its own opacity):
# one per board beat, in that beat's own empty corner, clear of the single part its sentence names.
# s3 deliberately carries none — see the "s3" note in PERCEPTO_PROPS below.
PERCEPTO_PROPS = {
    "s2": ("jack-o-lantern.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    # "s3": nothing, on purpose. s2 and s3 open the SAME recipe on the SAME board (alarm-button)
    # and both end holding the pushbutton, so the two beats are within a wire of being the same
    # picture twice. What separates them is the voice: s2 is [theatrical, relishing it] and s3 is
    # [plain and matter-of-fact] — the beat where the showman drops the act and admits the bench
    # has a buzzer where Castle had a motor. A Halloween cut-out sitting in the corner through the
    # honest beat is the costume the line just took off, and leaving it out gives the audience a
    # visual cue for the gear change that the wiring alone cannot. This is a taste call, not a
    # constraint: one line here puts a prop back if Seth wants the rule kept literally.
    "s4": ("zombie-hand.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s5": ("ghost.png", "bottom-left", 0.24, 0.45, 0.85, 0.85),
    "s6": ("mummy.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
}

# Per-trailer configuration for everything above that is not shared. Everything NOT in here — the
# theme, the board badge and its position, the prop treatment, the title-card duration, the end
# card's art — is the family's, and is deliberately not made configurable: two films in one pack
# that disagree about their own palette is a bug, not a feature.
# Per-beat prop treatment for the inventor films' four board beats (s2-s5), one tool per beat,
# using the five hand-drawn tool PNGs committed alongside the Halloween props at PROPS_DIR. The
# corner/height/opacity/brightness/saturate values are a first pass at the family's established
# default treatment (matching PROP_FOR's dense/saturated-art profile, not the pale-art "ghost"
# exception) — per PROPS_DIR's own comment ("chosen per beat by looking at that beat's actual
# recorded frame ... not a formula"), these are checked against real rendered frames and adjusted
# in the same pass that watches the frames per docs/film-pipeline.md's "open the frames" check.
# s2-s4 are history beats now told with art (see the art-model comments below) rather than a
# recorded shot, so they carry no corner prop — an illustration doesn't need one. Only s5 (the
# wired build) still records footage and keeps its prop.
VOLTA_PROPS = {
    "s5": ("nib-pen.png", "bottom-left", 0.24, 0.3, 0.5, 0.65),
}
OHM_PROPS = {
    "s2": ("multimeter.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s3": ("test-leads.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s4": ("nib-pen.png", "bottom-left", 0.24, 0.3, 0.5, 0.65),
    "s5": ("screwdriver.png", "bottom-left", 0.24, 0.3, 0.5, 0.65),
}
# exp-16 (Faraday's relay board): s2-s4 are the same unwired parts drawer (no `wire-it` in those
# shot chains — see content/trailers/inventor-michael-faraday.md), so any corner is free of the
# beat's own named part there. s5 is wired and running (a lit green LED plus a "Relay 9V" module
# occupy the grid's right-hand columns), so its props sit bottom-left, clear of both.
FARADAY_PROPS = {
    "s2": ("nib-pen.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s3": ("voltage-tester.png", "bottom-right", 0.24, 0.3, 0.5, 0.65),
    "s4": ("test-leads.png", "bottom-left", 0.24, 0.3, 0.5, 0.65),
    "s5": ("screwdriver.png", "bottom-left", 0.24, 0.3, 0.5, 0.65),
}

# Latimer: s1–s4 are art: beats (the illustration is the atmosphere a prop would add); s5, the
# wired lamp, is a lamp-glow beat where no tool prop fits.
LATIMER_PROPS = {}


# The town film's props (#92), deliberately thin. video-guidelines.md wants props in view, but the
# brief for this film is "the street is the picture": six of its ten beats are the town page, which
# is already a drawn scene with six shopfronts in it, and a floating tool in the corner of a street
# would read as a sticker on a painting rather than as set dressing. So the street beats carry
# none, and only the four bench beats do — one period-plausible tool each, in that beat's own empty
# corner, at 24% of frame height — see the treatment note below for the opacity numbers.
#
# Which tool, per beat, follows the line rather than a rotation: s3 is the boy asking what the
# parts are, so a voltage tester (the thing you would be handed to find out); s5 is the manual open
# to experiment one on the garage bench, so the nib pen that marks up a manual — Ray's own pencil
# on project forty-one is s9's line, and this plants it; s9 is the loop closing, so test leads; s10
# is the one number the film has been walking toward (560 mA cold, 63 mA settled), so the
# multimeter. s3/s5 open the unwired exp-1 board and s9/s10 the lamp recipe; bottom-right is clear
# board in the first pair and bottom-left in the second, where the lit lamp and its wiring sit
# right of centre. Checked against the real recorded frames, not assumed.
# Treatment: the ghost's numbers (0.45 opacity, 0.85 brightness, 0.85 saturate), not the
# jack-o-lantern's (0.3/0.5/0.65). Same reason PROP_FOR raises the ghost alone: these five tool
# PNGs are pale, low-saturation ink line art with no solid fill, and the darker profile washes them
# out to almost nothing against the near-black board. Checked on a real rendered frame of this
# film's s3 at 0.3/0.5/0.65 — the voltage tester was whole and in frame and effectively invisible,
# a few faint lines you only find if you know where to look, which is not set dressing. Seth's
# mid-round-8 correction on PROP_FOR is the standing ruling: "clearly present, not hiding in a gap."
OHMSVILLE_PROPS = {
    "s3": ("voltage-tester.png", "bottom-right", 0.24, 0.45, 0.85, 0.85),
    "s5": ("nib-pen.png", "bottom-right", 0.24, 0.45, 0.85, 0.85),
    "s9": ("test-leads.png", "bottom-left", 0.24, 0.45, 0.85, 0.85),
    "s10": ("multimeter.png", "bottom-left", 0.24, 0.45, 0.85, 0.85),
}

TRAILERS = {
    "people-of-ohmsville": {
        "family": "profiles",
        "music": PROFILES_MUSIC,
        # No corner props. Seven of this film's twenty beats are a person's face at the size of the
        # frame, and the rest are the town film's own illustrations, which "are already the
        # atmosphere a prop would otherwise add" (the art branch's own note). A tool dimmed into
        # the corner of somebody's interview is a sticker on a photograph.
        "props": {},
        # Nine of the eleven pictures are the town film's, reused rather than regenerated: the two
        # street parallaxes, its three generated clips and four of its stills. Only
        # classroom-desks.png and sign-in-sheets.png - the teller's room and what the listener is
        # holding - are this film's own, and they live in its own directory.
        "art_from": "ohmsville",
        # Both of these are on screen at 0:00, checked on a real frame. What s1 does NOT use is the
        # family's `title_card_art_file`: it carries its own `art:` (the teller's classroom), and
        # the title branch prefers a beat's own illustration to the family's plate. The text is the
        # script's own `title:` and the house kicker, like every other row.
        "title_card": {"title": "The People of Ohmsville", "kicker": "OHMSVILLE"},
        # Matched to the closing narration word for word ("These are made-up people in a made-up
        # town. The kit is real.") - show it while she says it.
        "end_card": {"title": "Made-Up People", "kicker": "A MADE-UP TOWN - THE KIT IS REAL"},
    },
    "spooky-shack": {
        "family": "halloween",
        "music": SPOOKY_SHACK_MUSIC,
        "props": PROP_FOR,
        "title_card": {"title": TITLE_CARD_TITLE, "kicker": TITLE_CARD_KICKER},
        "end_card": {"title": "Spooky Shack", "kicker": "THE OCTOBER MISSION"},
    },
    "percepto": {
        "family": "halloween",
        "music": SPOOKY_SHACK_MUSIC,
        "props": PERCEPTO_PROPS,
        # The title is the script's own `title:` frontmatter; the kicker stays at the house name
        # rather than describing the pack, because "Percepto" is a reveal this film spends its
        # second beat earning and the end card is where the offer belongs.
        "title_card": {"title": "Back When the Scares Were Wired", "kicker": "OHMSVILLE"},
        # Matched to the closing narration word for word ("The Spooky Science Lab, opening the
        # first of October") — show it while he says it. "Spooky Science Lab" is the campaign's
        # own `title` in client/src/kit/campaigns.ts, not a name invented for the card.
        "end_card": {"title": "Spooky Science Lab", "kicker": "OPENING THE FIRST OF OCTOBER"},
    },
    "inventor-alessandro-volta": {
        "family": "inventors",
        "music": INVENTORS_MUSIC,
        "props": VOLTA_PROPS,
        # title_card is unused for this film: s1 is `shot: none` (content/trailers/
        # inventor-alessandro-volta.md), so main()'s title-card carve — which only fires inside
        # the `if s["shot"]:` branch — never runs; s1 instead falls through to the card-kind
        # fallback branch (a path the Halloween trailers never exercise; see its own comment).
        # Set anyway for interface parity with every other TRAILERS row, using the script's own
        # `title:` frontmatter and the house kicker (no campaign reveal to withhold, unlike
        # Percepto).
        "title_card": {"title": "The Twitch That Wasn't in the Frog", "kicker": "OHMSVILLE"},
        # Matched word for word to the shared closing narration ("Ten inventors, each with a build
        # already on the board. Ohmsville dot com.") — both inventor films share this line, so both
        # end cards share this text; there is no per-film campaign name to reveal here.
        "end_card": {"title": "Ten Inventors", "kicker": "OHMSVILLE.COM"},
    },
    "inventor-georg-ohm": {
        "family": "inventors",
        "music": INVENTORS_MUSIC,
        "props": OHM_PROPS,
        # See inventor-alessandro-volta's own comment: unused for the same reason (s1 is
        # `shot: none` in content/trailers/inventor-georg-ohm.md too).
        "title_card": {"title": "Does a Wire Have a Mind of Its Own", "kicker": "OHMSVILLE"},
        "end_card": {"title": "Ten Inventors", "kicker": "OHMSVILLE.COM"},
    },
    "inventor-michael-faraday": {
        "family": "inventors",
        "music": INVENTORS_MUSIC,
        "props": FARADAY_PROPS,
        # See inventor-alessandro-volta's own comment: unused for the same reason (s1 is
        # `shot: none` in content/trailers/inventor-michael-faraday.md too).
        "title_card": {"title": "The Coil That Only Wakes Up Once", "kicker": "OHMSVILLE"},
        "end_card": {"title": "Ten Inventors", "kicker": "OHMSVILLE.COM"},
    },
    "inventor-lewis-latimer": {
        "family": "inventors",
        "music": INVENTORS_MUSIC,
        "props": LATIMER_PROPS,
        "title_card": {"title": "The Bulb That Wouldn't Stay Lit", "kicker": "OHMSVILLE"},
        "end_card": {"title": "Ten Inventors", "kicker": "OHMSVILLE.COM"},
    },
    "ohmsville": {
        "family": "ohmsville",
        "music": OHMSVILLE_MUSIC,
        "props": OHMSVILLE_PROPS,
        # The title is the script's own `title:` frontmatter and the kicker its own `kicker:` key
        # ("MAIN STREET - ONE STREET, FOUR DECADES"), which is what the card is a picture of. No
        # reveal is being withheld the way Percepto withholds its campaign name: this film says
        # what it is in its first line.
        "title_card": {"title": "Ohmsville", "kicker": "MAIN STREET \u00b7 ONE STREET, FOUR DECADES"},
        # Word for word the script's own `endcard:`/`endkicker:` frontmatter, which is itself word
        # for word the closing narration ("Ohmsville is a made-up town. The kit is real.") — show it
        # while he says it, the same rule Percepto's end card follows.
        "end_card": {"title": "Ohmsville", "kicker": "OHMSVILLE IS A MADE-UP TOWN \u00b7 THE KIT IS REAL"},
    },
}


def art_source(trailer_id: str, name: str) -> Path:
    """Where a picture named in a script actually lives.

    A film's own asset directory first, then the directory named by its TRAILERS row's `art_from`,
    if it has one. #92's second film is the reason this exists: nine of its eleven pictures are the
    town film's own stills, clips and parallax planes, reused as they are. Copying them into a
    second directory would put the same generated picture on disk twice with nothing keeping the
    copies in step, and the alternative - regenerating them - would pay twice for the same art.
    A film with no `art_from` resolves exactly where it always did.
    """
    own = PROJECT / "assets" / "art" / trailer_id / name
    if own.is_file():
        return own
    shared = TRAILERS[trailer_id].get("art_from")
    if shared:
        borrowed = PROJECT / "assets" / "art" / shared / name
        if borrowed.is_file():
            return borrowed
    raise RuntimeError(f"{trailer_id}: no picture called {name!r} in its own assets"
                       + (f" or in {shared}'s" if shared else ""))


def interview_labels() -> dict:
    """{slug: (name, trade)}, read off the Ohmsville repo's own client/src/site/people.ts.

    The same table scripts/persona-interview-composite.sh reads for the profile films' own lower
    thirds, so the name under a face in the documentary and the name under that same face in the
    person's own film cannot drift apart. Parsed rather than imported for the same reason
    check_render.py reads the narration manifest as text: it is one small lookup, and this is a
    Python script on the other side of a repo boundary.
    """
    src = (OHMSVILLE / "client" / "src" / "site" / "people.ts").read_text()
    out = {}
    for block in src.split("slug: '")[1:]:
        slug = block.split("'", 1)[0]
        name = re.search(r"name: '([^']*)'", block)
        trade = re.search("trade: (?:'([^']*)'|\"([^\"]*)\")", block)
        if name and trade:
            out[slug] = (name.group(1), trade.group(1) or trade.group(2))
    if not out:
        raise RuntimeError("no people found in client/src/site/people.ts - its shape must have "
                           "changed; this function reads it, it does not guess")
    return out


def interview_segments(trailer_id: str) -> dict:
    """What cut_interview_segments.py cut for this film, keyed by beat id.

    Empty for every film that has no interview beats, which is every film but one. The record is
    the authority on how long each of those beats runs: the seconds are ffprobe's, measured off the
    segment that was actually written, never the EDL's planned window.
    """
    record = PROJECT / "assets" / "art" / trailer_id / "segments.json"
    if not record.is_file():
        return {}
    # Keyed by "<film> <section>" — what the script's own `interview:` line says — and never by the
    # beat id. Beat ids renumber every time a draft inserts a beat, and a lookup on them turns a
    # rewrite into seven orphaned segments and a failed render, which is exactly how draft 2 of
    # this film first broke.
    return {f'{x["profile"]} {x["section"]}': x for x in json.loads(record.read_text())["segments"]}


def motion_amount(seconds: float) -> float:
    """How far a still's camera move travels over a beat of this length.

    imageTransform completes exactly one pass of its named move across the cut, so with a fixed
    amplitude the longer the beat the slower the camera — backwards, and measurable: on the first
    draft-4 render s3 (11.1s, push-in) had a longest static run of 0.10s and s7 (18.4s, pull-out)
    had 17.20s, same code and same 12%, because s7's night street has far less contrast for a
    sub-pixel zoom to move than s3's board does.

    0.02 per second, clamped. The floor is the old fixed 0.12, which this reproduces exactly at
    six seconds, so no existing beat gets a smaller move than it had. The ceiling is 0.34, past
    which a push-in is cropping away a third of the picture to get its motion.
    """
    return round(min(0.34, max(0.12, 0.02 * seconds)), 3)


def detect_letterbox(src: Path) -> str:
    """The `crop=` filter that removes a generated clip's own black padding, measured not assumed.

    Veo returns a 1920x1080 file whose picture is 1620x1080 centred — it preserves the 1.5:1 aspect
    of the start frame rather than filling 16:9 — so three of this film's eight beats would
    otherwise carry 150px of bare black either side, which is both ugly and the exact thing
    check_render.py's bare-background check exists to catch. cropdetect over two seconds in the
    middle of the clip, most frequent answer wins; a clip that really is full-frame yields
    `crop=<its own size>:0:0` and nothing is lost.
    """
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", "2", "-t", "2", "-i", str(src),
         "-vf", "cropdetect=24:2:0", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    found = re.findall(r"crop=(\d+:\d+:\d+:\d+)", proc.stderr)
    if not found:
        raise RuntimeError(f"cropdetect said nothing about {src.name} — cannot tell picture from padding")
    return "crop=" + Counter(found).most_common(1)[0][0]


def loop_clip(src: Path, dest: Path, seconds: float) -> None:
    """Make a five-second generated clip last a beat, without ever freezing on a frame.

    Not `-stream_loop` on the clip itself: that hard-cuts back to frame 0 every five seconds, which
    reads as a dropped shot. Forward-then-reversed does not — the motion simply runs back the way
    it came — and because the bounce ends on the frame it started on, looping THAT is seamless. The
    duplicated frame at the turn (forward's last is reverse's first) is trimmed, or the pivot
    stutters for a frame.

    Also where the clip is normalised to the delivered frame: generated video arrives at 720p and
    at whatever frame rate the model chose, and every other cut in this film is 1920x1080 at 30.
    """
    crop = detect_letterbox(src)
    bounce = dest.with_name(dest.stem + "-bounce.mp4")
    run_ffmpeg([
        "ffmpeg", "-y", "-i", str(src), "-filter_complex",
        f"[0:v]{crop},split[a][b];[b]reverse,trim=start_frame=1,setpts=PTS-STARTPTS[r];[a][r]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-pix_fmt", "yuv420p", str(bounce),
    ])
    run_ffmpeg([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(bounce), "-t", f"{seconds:.3f}",
        # cover, not stretch: the picture inside a generated clip keeps the 1.5:1 aspect of the
        # still it grew out of, and every `art:` still in this film is fitted the same way
        # (object-fit: cover in ImageCut). Filling by distortion would make one beat's people a
        # different shape from the next beat's.
        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,"
               "crop=1920:1080,fps=30",
        "-an",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-movflags", "faststart", str(dest),
    ])
    bounce.unlink()
    if not dest.is_file() or dest.stat().st_size < 50_000:
        raise RuntimeError(f"looping {src.name} to {seconds:.1f}s produced nothing usable")


def snapshot(trailer_id: str, dest: Path) -> dict:
    """Copy the recorder's output for `trailer_id` to `dest` and return its shotlist.

    Same snapshot-then-validate dance as build_lesson.py's main(), for the same reason: the
    recorder writes shotlist.json last, so a naive copytree can silently miss it mid-write.
    Extracted from main() unchanged so build_box_film.py reads the recorder the same way rather
    than keeping a second copy of the retry loop.
    """
    live_shots = OHMSVILLE / "client" / ".shots" / "trailers" / trailer_id
    for attempt in range(5):
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(live_shots, dest)
            shotlist = json.loads((dest / "shotlist.json").read_text())
            missing = [
                s["shot"]["file"] for s in shotlist["sections"]
                if s.get("shot") and not (dest / s["shot"]["file"]).is_file()
            ]
            if missing:
                raise FileNotFoundError(f"snapshot missing shot file(s): {missing}")
            return shotlist
        except (FileNotFoundError, json.JSONDecodeError, shutil.Error, KeyError) as e:
            if attempt == 4:
                raise RuntimeError(
                    f"could not get a complete, stable snapshot of {live_shots} after "
                    f"5 tries — the shot recorder is still actively rewriting it: {e}"
                ) from e
            print(f"snapshot attempt {attempt + 1} caught the recorder mid-write ({e}); retrying in 5s", file=sys.stderr)
            time.sleep(5)
    raise AssertionError("unreachable: the loop above either returns or raises")


def stage(trailer_id: str) -> Path:
    out = PUBLIC / trailer_id
    if out.exists():
        shutil.rmtree(out)
    (out / "narration").mkdir(parents=True)
    (out / "shots").mkdir()
    (out / "props").mkdir()
    (out / "logo").mkdir()
    (out / "art").mkdir()
    return out


def main(trailer_id: str) -> None:
    if trailer_id not in TRAILERS:
        raise SystemExit(f"no configuration for trailer {trailer_id!r} — add a row to TRAILERS "
                         f"(known: {', '.join(sorted(TRAILERS))})")
    cfg = TRAILERS[trailer_id]
    props_for = cfg["props"]
    music = cfg["music"]
    family = FAMILIES[cfg.get("family", "halloween")]

    art = PROJECT / "artifacts" / f"trailer-{trailer_id}"
    transcript_dir = art / "transcripts"
    art.mkdir(parents=True, exist_ok=True)

    shots = art / "_source_snapshot"
    shotlist = snapshot(trailer_id, shots)
    out = stage(trailer_id)
    # Empty for every film without interview beats, which is every film but the documentary.
    segments = interview_segments(trailer_id)
    labels = interview_labels() if segments else {}

    # Stage the title card's prop, this trailer's board-beat props, the board badge (all permanent
    # assets), and the end card's art (fresh from the live site each render — see END_CARD_ART's
    # own comment).
    shutil.copy(PROPS_DIR / family["title_card_art_file"], out / "props" / family["title_card_art_file"])
    for filename, _corner, _height_frac, _opacity, _brightness, _saturate in props_for.values():
        shutil.copy(PROPS_DIR / filename, out / "props" / filename)
    shutil.copy(LOGO_DIR / BOARD_BADGE, out / "logo" / BOARD_BADGE)
    end_card_source = OHMSVILLE / "client" / "public" / Path(*family["end_card_source"])
    if not end_card_source.is_file():
        raise RuntimeError(f"end card art missing at {end_card_source}")
    shutil.copy(end_card_source, out / END_CARD_ART)

    # The anim model (docs/film-pipeline.md's "Inventor films" section, Seth's second ruling):
    # a beat may also carry one or more `anim:` overlay clips — a fixed-library Remotion animation
    # (current-flow, resistance, voltage-push, symbol-reveal, pile-stack, lamp-glow) played over a
    # dimmed version of that beat's own base cut (its `shot:` or `art:`), never alone. Kept in a
    # SEPARATE top-level list rather than folded into `cuts`, because check_render.py's
    # check_contiguity() requires strict adjacency between cuts (every out_seconds ==
    # the next cut's in_seconds) and an overlay is meant to overlap its base cut in time, not sit
    # next to it. OhmsvilleLesson.tsx renders `overlays` as additional <Sequence>s painted after
    # the main cuts.map(...) loop, so they draw on top by DOM order alone.
    cuts, words, overlays = [], [], []
    sections = shotlist["sections"]
    t = 0.0
    for i, s in enumerate(sections):
        audio = out / "narration" / f"{s['id']}.mp3"
        # An interview beat's audio is not narration and was never bought: it is the segment's own
        # track, cut out of that persona's profile film by cut_interview_segments.py. Laid into the
        # bed here under the same name every other beat's narration uses, so the concat, the
        # caption pass and the timeline arithmetic below are the identical code path.
        iv = s.get("interview")
        seg = segments.get(f'{iv["film"]} {iv["section"]}') if iv else None
        if seg:
            shutil.copy(PROJECT / "assets" / "art" / trailer_id / seg["audio"], audio)
        elif s.get("audio"):
            shutil.copy(s["audio"], audio)
        else:
            raise RuntimeError(f"{s['id']}: no narration and no interview segment — nothing to play")

        # Same timeline-from-measured-audio fix as build_lesson.py: derive start/end from THIS
        # clip's own ffprobe duration, never shotlist.json's upstream-computed seconds.
        real_dur = ffprobe_duration(audio)
        start = t
        end = start + real_dur
        t = end + SECTION_GAP_SECONDS
        for w in captions_for(s, audio, transcript_dir):
            words.append({"word": w["word"], "startMs": int(start * 1000) + w["startMs"],
                          "endMs": int(start * 1000) + w["endMs"], "liftPx": 0})

        # The art model (docs/film-pipeline.md's "Inventor films" section): a beat may carry its
        # own illustration instead of a recorded shot — Volta/Ohm's history beats, where the board
        # has nothing to show. Staged once here so both the title branch (s1, kind "title") and the
        # new image branch (s2-s4, kind "none") below can reference the file without re-copying it.
        if s.get("art"):
            shutil.copy(art_source(trailer_id, s["art"]["file"]), out / "art" / s["art"]["file"])

        # The parallax model (#92 draft 4): a beat's planes, staged the same way a single `art:`
        # still is and out of the same directory, because they are the same kind of asset — a
        # generated picture with no recording behind it. The compositor's ParallaxCut slides them
        # at different rates; this script only has to put them where it can find them.
        for layer in (s.get("parallax") or {}).get("layers", []):
            shutil.copy(art_source(trailer_id, layer), out / "art" / layer)

        # videoScript.ts's parseAnim already refuses an `anim:` with no `shot:`/`art:` to dim under
        # (fail(file, where, 'anim needs a "shot:" or "art:" to dim under it')), so by the time an
        # anim reaches this script its beat is guaranteed to have a base cut. Multiple anims on one
        # beat play in written order over that same base (Volta's s3: pile-stack then
        # voltage-push), so they're laid back-to-back starting at the beat's own start rather than
        # each spanning the whole beat.
        if s.get("anim"):
            a_t = start
            for j, a in enumerate(s["anim"]):
                overlays.append({
                    "id": f"{s['id']}-anim{j}", "kind": a["kind"],
                    "in_seconds": round(a_t, 2), "out_seconds": round(a_t + a["dur"], 2),
                    "props": a.get("props", {}),
                })
                a_t += a["dur"]

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
                    "title": cfg["title_card"]["title"], "kicker": cfg["title_card"]["kicker"],
                    "art": f"ohmsville-trailers/{trailer_id}/props/{family['title_card_art_file']}",
                })
                video_start = start + TITLE_CARD_SECONDS
                source_start += TITLE_CARD_SECONDS
            prop, prop_corner, prop_height_frac, prop_opacity, prop_brightness, prop_saturate = props_for.get(
                s["id"], (None, None, None, None, None, None)
            )
            cuts.append({
                "id": s["id"], "type": "video", "layer": 0,
                "src": f"ohmsville-trailers/{trailer_id}/shots/{s['shot']['file']}",
                "in_seconds": round(video_start, 2), "out_seconds": round(end, 2),
                "sourceStartSeconds": source_start,
                "label": None,  # no lower-third: a trailer names nothing the narration hasn't already said
                **({
                    "prop": f"ohmsville-trailers/{trailer_id}/props/{prop}",
                    "propCorner": prop_corner, "propHeightFrac": prop_height_frac, "propOpacity": prop_opacity,
                    "propBrightness": prop_brightness, "propSaturate": prop_saturate,
                } if prop else {}),
            })
        elif s.get("interview"):
            # The interview model (#92 film 2): a beat that is a section of somebody's own profile
            # film, playing with that film's own audio. Three things separate it from every clip
            # branch above, and all three are already handled by the time the cut is written:
            #
            #   - its audio is the segment's, laid into the narration bed at the top of this loop,
            #     so `start`/`end` here are derived from the segment's real ffprobe duration
            #     exactly as every other beat's are derived from its narration's;
            #   - it is NOT looped. loop_clip exists because a generated clip is five seconds and a
            #     beat is not; a segment is precisely as long as its own beat, because the beat was
            #     built from it. Bouncing a talking head would run somebody's sentence backwards.
            #   - it carries a lower third, which no other trailer cut does ("a trailer names
            #     nothing the narration hasn't already said" — but here the narration is somebody
            #     else's voice arriving with no introduction, so the name IS the introduction).
            #
            # cut_interview_segments.py already normalised the picture to 1920x1080 at 30fps, so
            # staging is a copy and the existing "video" cut type renders it unchanged.
            iv = s["interview"]
            key = f'{iv["film"]} {iv["section"]}'
            if key not in segments:
                raise RuntimeError(f"{s['id']}: the script asks for {key}, which cut_interview_"
                                   f"segments.py has not cut — re-run it for this film")
            seg = segments[key]
            shutil.copy(PROJECT / "assets" / "art" / trailer_id / seg["file"], out / "art" / seg["file"])
            who = labels.get(seg["slug"])
            if not who:
                raise RuntimeError(f"{s['id']}: nobody with slug {seg['slug']!r} in people.ts, so "
                                   f"this face would go on screen unnamed")
            cuts.append({
                "id": s["id"], "type": "video", "layer": 0,
                "src": f"ohmsville-trailers/{trailer_id}/art/{seg['file']}",
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "sourceStartSeconds": 0.0,
                "label": f"{who[0]} · {who[1]}",
            })
        elif s.get("clip"):
            # The clip model (#92 draft 4): a generated five-second video in place of a recorded
            # shot, for the beats Seth named as the film's hero moments (the kid at the counter,
            # the front door on a Saturday, the four shops going dark). The generated file is
            # never the beat's own length, so it is looped out to it HERE rather than in the
            # composition: the staged mp4 is already exactly as long as the beat, which means the
            # existing "video" cut type renders it with no change to OhmsvilleLesson.tsx at all.
            staged = out / "art" / s["clip"]
            loop_clip(art_source(trailer_id, s["clip"]), staged, end - start)
            video_start = start
            source_start = 0.0
            # Same title carve as the shot branch above, for the same reason: s1's first
            # TITLE_CARD_SECONDS are the card, and the clip picks up from that point in its own
            # source rather than replaying the seconds the card covered.
            if i == 0 and end - start > TITLE_CARD_SECONDS:
                cuts.append({
                    "id": f"{s['id']}-title", "type": "title", "layer": 0,
                    "in_seconds": round(start, 2), "out_seconds": round(start + TITLE_CARD_SECONDS, 2),
                    "title": cfg["title_card"]["title"], "kicker": cfg["title_card"]["kicker"],
                    "art": f"ohmsville-trailers/{trailer_id}/props/{family['title_card_art_file']}",
                })
                video_start = start + TITLE_CARD_SECONDS
                source_start = TITLE_CARD_SECONDS
            cuts.append({
                "id": s["id"], "type": "video", "layer": 0,
                "src": f"ohmsville-trailers/{trailer_id}/art/{s['clip']}",
                "in_seconds": round(video_start, 2), "out_seconds": round(end, 2),
                "sourceStartSeconds": source_start,
                "label": None,
            })
        elif s.get("parallax"):
            cuts.append({
                "id": s["id"], "type": "parallax", "layer": 0,
                "layers": [f"ohmsville-trailers/{trailer_id}/art/{f}" for f in s["parallax"]["layers"]],
                "parallaxDirection": s["parallax"]["direction"],
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "label": None,
            })
        elif s["card"]["kind"] == "end" and cuts:
            # The trailer's closing section (kind: end, shot: none) has no footage of its own —
            # its narration is the voiceover for the closing card, so the last real shot holds
            # through it (same fix as build_lesson.py's own end-card handling), and
            # OhmsvilleLesson.tsx's endCard synthesis adds the actual plate afterward, silent.
            cuts[-1]["out_seconds"] = round(end, 2)
        elif s["card"]["kind"] == "title":
            # No footage recorded for this beat (an inventor film's cold open, e.g. Volta/Ohm's
            # s1, has no board shot to hold — unlike Spooky Shack/Percepto's s1, which always has
            # one). Without a video underneath, the title card must cover the WHOLE beat instead
            # of just its opening TITLE_CARD_SECONDS, using the same art/title/kicker as the
            # shot-branch's title-carving above. Skipping "art" here is the bug this comment
            # replaces: OhmsvilleLesson.tsx's TitlePlate renders text over the bare theme
            # background when "art" is absent, which the bare-background check correctly flags.
            # A beat with its own per-beat illustration (s.get("art")) uses that in place of the
            # family's generic title_card_art_file — Volta's s1 is "the hook", not a portrait of
            # the family's whole card, so the frog's-leg scene belongs here instead.
            title_art = (f"ohmsville-trailers/{trailer_id}/art/{s['art']['file']}" if s.get("art")
                        else f"ohmsville-trailers/{trailer_id}/props/{family['title_card_art_file']}")
            cuts.append({
                "id": s["id"], "type": "title", "layer": 0,
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "title": cfg["title_card"]["title"], "kicker": cfg["title_card"]["kicker"],
                "art": title_art,
                # #92 draft 5: a title beat carrying its OWN illustration is a picture beat that
                # happens to have words over it, so it gets the same Ken Burns the `art:` branch
                # below gives every other still. Without this the plate is frozen for the whole
                # beat — measured at 2.73s of held frame on draft 5's first cut, against the 1.0s
                # limit. The family's generic title_card_art_file keeps no motion: it is a plate,
                # not a scene, and every inventor film's s1 renders exactly as it did before.
                **({"motion": s["art"]["motion"], "motionAmount": motion_amount(end - start)}
                   if s.get("art") else {}),
            })
        elif s.get("art"):
            # The art model's plain case: a beat with an illustration and no card kind (Volta/Ohm's
            # s2-s4 — the people, the argument, what it cost). The compositor renders the image
            # full-bleed with its own named camera motion (hold/push-in/drift-left/drift-right/
            # pull-out) under the beat's captions, in place of a recorded shot. No prop overlay:
            # the illustration is already the atmosphere a prop would otherwise add.
            cuts.append({
                "id": s["id"], "type": "image", "layer": 0,
                "src": f"ohmsville-trailers/{trailer_id}/art/{s['art']['file']}",
                "motion": s["art"]["motion"],
                "motionAmount": motion_amount(end - start),
                "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                "label": None,
            })
        else:
            # Still-defensive fallback (a shot-less section that is neither "end" nor "title") —
            # not currently exercised by any trailer.
            cuts.append({"id": s["id"], "type": s["card"]["kind"], "layer": 0,
                         "in_seconds": round(start, 2), "out_seconds": round(end, 2),
                         "title": shotlist["title"], "label": None})

    # Bridge the SECTION_GAP_SECONDS breath between one beat's narration and the next: `t` above
    # advances by that gap after every section, but nothing filled the picture for it, so every
    # ordinary cut-to-cut boundary left a real hole between one cut's out_seconds and the next
    # cut's in_seconds — no Sequence active, the plain theme background showing through with
    # whatever caption text hadn't yet been replaced (looks exactly like a dropped shot). Caught by
    # sampling real frames across the whole film: all five beat boundaries did it, not just s3's.
    # The fix already used for the end card (holding cuts[-1] through its own trailing narration,
    # above) generalizes here: every cut holds its last frame until the next cut actually begins.
    # This only pulls existing gaps closed — it never extends past the final cut, so total runtime
    # (and everything build_lesson.py's shared helpers compute from it) is unchanged.
    for i in range(len(cuts) - 1):
        if cuts[i]["out_seconds"] < cuts[i + 1]["in_seconds"]:
            cuts[i]["out_seconds"] = cuts[i + 1]["in_seconds"]

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
    if not music.exists():
        raise RuntimeError(
            f"trailer music bed missing at {music} — generate it once with "
            f"music_gen (see the fix report for the prompt) and save it there before rendering"
        )
    render_seconds = total_seconds + end_card_seconds
    run_ffmpeg([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(music),
        "-t", f"{render_seconds:.3f}", "-c:a", "libmp3lame", "-q:a", "4",
        str(out / "music.mp3"),
    ])

    # The board badge's position is a per-recipe judgement call (where the top row actually has
    # room), made by looking at real recorded frames, not guessed from CSS — see BOARD_BADGE_POSITION's
    # own comment for what was checked and why.
    theme = {**family["theme"], "boardBadge": f"ohmsville-trailers/{trailer_id}/logo/{BOARD_BADGE}",
             "boardBadgePosition": BOARD_BADGE_POSITION}

    props = {
        "fps": 30, "width": 1920, "height": 1080,
        "themeConfig": theme,
        "cuts": cuts,
        "overlays": overlays,
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
            "title": cfg["end_card"]["title"], "kicker": cfg["end_card"]["kicker"],
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
