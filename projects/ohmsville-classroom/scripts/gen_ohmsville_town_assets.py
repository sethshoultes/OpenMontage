#!/usr/bin/env python3
"""Generate the town film's scenes (#92 draft 4).

    python projects/ohmsville-classroom/scripts/gen_ohmsville_town_assets.py --list
    python projects/ohmsville-classroom/scripts/gen_ohmsville_town_assets.py bench-first-wire
    python projects/ohmsville-classroom/scripts/gen_ohmsville_town_assets.py --all

Draft 3 of the town film was recorded off the live site: the same two screens for four minutes, a
street that never moved. Seth's ruling was to source the pictures instead - "do parallax or Ken
Burns effects on generated scenes. Start generating scenes." This script is that: every beat of
`content/trailers/ohmsville.md` is a generated picture, and each one carries its own motion.

Three kinds of asset, matching the three beat kinds the script authors:

  still     one opaque 16:9 illustration, moved in the compositor by its beat's `motion:` word
            (the art model's Ken Burns, already in OhmsvilleLesson.tsx's imageTransform).
  layer     one image per parallax plane. The sky plane is opaque; the shopfront row and the
            foreground props are generated with a transparent background so the planes behind
            them show through as they slide at different rates.
  clip      a five-second generated video. Generated as image_to_video from a still made by this
            same script, so the clip opens in exactly the palette and hand the stills are in
            rather than whatever a text prompt alone lands on. build_trailer.py loops it
            (forward, reversed, forward...) out to the beat's own length.

Every asset writes its prompt next to itself as `<name>.prompt.txt`, and every call appends to
`costs.md` in the same directory. BUDGET_USD is a hard stop: the script refuses a call that would
cross it rather than discovering the overrun afterwards.
"""
from __future__ import annotations

import argparse
import base64
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
# The film this run is generating for. The town film is the default and the only one this script
# had until #92's second film needed two stills of its own; `--film people-of-ohmsville` points
# ART, COSTS and ASSETS at that film's directory and its own short asset table instead. Nothing
# about a run without the flag changes.
FILM = "ohmsville"
ART = PROJECT / "assets" / "art" / FILM
COSTS = ART / "costs.md"

BUDGET_USD = 30.0

sys.path.insert(0, str(ROOT))
from tools.tool_registry import registry  # noqa: E402

registry.discover()

# The house look, in front of every prompt. "No text" is not a preference here: the film's own
# captions carry every word, and a generated sign is the fastest way to put a misspelled or
# trademarked name on screen. docs/brand/OHMSVILLE.md's "shops are homages, never replicas".
STYLE = (
    "Hand-drawn editorial illustration of small-town America, flat and matte, in the style of a "
    "1970s hobby-kit box lid: heavy charcoal ink outlines, flat fills with a little paper grain, "
    "no gradients, no photographic realism, no lens flare, no 3D render. "
    "Palette: kraft brown, plywood tan, burnt orange, warm cream, muted teal sky, deep charcoal. "
    "Absolutely no text, no letters, no numbers, no signage lettering, no logos, no brand names, "
    "no recognizable real-world storefronts. No recognizable real person's face: figures are seen "
    "from behind, in silhouette, or with the face turned away. "
)

# 1536x1024 is gpt-image-2's widest size (1.5:1). The frame is 1.778:1, so the compositor's
# object-fit: cover crops a little top and bottom - composed for, not fought.
SIZE = "1536x1024"

ASSETS: dict[str, dict] = {
    # ---- s3, s7: stills the compositor pans over (the art model) ----------------------------
    "bench-first-wire": {
        "kind": "still",
        "beat": "s3",
        "prompt": (
            "A close, warm view down onto a 1970s electronics project board lying on a cluttered "
            "garage workbench under a gooseneck lamp. The board has a varnished plywood frame and "
            "tidy rows of small coiled brass spring terminals. One short red jumper wire has just "
            "been hooked between two neighbouring springs, and a child's hand is withdrawing from "
            "it at the edge of the frame. An open paper manual lies beside the board with a yellow "
            "pencil across it. Night outside the window, one pool of warm lamplight, everything "
            "else falling into kraft-brown shadow."
        ),
    },
    "garage-lamp": {
        "kind": "still",
        "beat": "s7",
        "prompt": (
            "Night, seen from the dark driveway of a small-town house: a detached single-car "
            "garage with its door rolled up, and the only light on the whole street coming from "
            "inside it. On the workbench in that light sits the same 1970s project board with its "
            "plywood frame and rows of spring terminals, an open manual, and a small lamp that is "
            "lit. The rest of the street is deep blue-black silhouette - rooflines, a leaning "
            "basketball hoop, a telephone pole. Warm orange light spilling out onto the concrete."
        ),
    },
    "lamp-lit": {
        "kind": "still",
        "beat": "s8",
        "prompt": (
            "A very close view of one corner of a 1970s electronics project board on a workbench at "
            "night: two rows of small coiled brass spring terminals, a short red jumper wire and a "
            "short black one hooked between them, a slide switch, a battery holder with two cells, "
            "and a small clear bulb in a holder that is lit - the filament a bright warm thread "
            "inside the glass, throwing a pool of orange light across the plywood and the nearest "
            "springs. Everything beyond that pool falls away into deep brown shadow. No hands, no "
            "faces, no room - just the lit corner of the board."
        ),
    },
    # ---- draft 5: the two pictures the telling needed and draft 4 did not have ----------------
    # Seth on draft 4: "You need a little bit of background - who's speaking or why they're there."
    # The film now opens in Ray's own garage with the listener sitting down, so it needs the room he
    # is standing in (bench-now, which is also the title card's art), and it spends a beat on what
    # was actually inside the lid, which the wide over-the-shoulder counter clip cannot get close
    # enough to marvel at (kit-open-counter).
    "bench-now": {
        "kind": "still",
        "beat": "s1",
        "prompt": (
            "Inside a small-town garage workshop at night, seen from a low stool across the bench: "
            "a scarred plywood workbench under one gooseneck lamp, and in the middle of it an open "
            "1970s hobby-kit box - varnished plywood frame, tidy rows of small coiled brass spring "
            "terminals, its lid standing up and away from the camera - with a well-thumbed paper "
            "manual open beside it and a pencil laid across the page. A second wooden stool pulled "
            "up on the near side, an enamel mug going cold, a soldering iron in its stand, a coffee "
            "can of resistors. Behind the bench, the pulled-down roll-up door, a pegboard of hand "
            "tools, and the dark of the rest of the garage. No people in frame, no hands. One warm "
            "pool of lamplight on the box, everything else deep kraft-brown shadow, with generous "
            "unlit space above the bench."
        ),
    },
    "kit-open-counter": {
        "kind": "still",
        "beat": "s3",
        "prompt": (
            "A close, near-overhead view down into a 1970s hobby electronics kit lying open on a "
            "shop counter, the way a nine-year-old sees it from tiptoe: the varnished plywood frame "
            "filling most of the frame, and inside it row upon row of small coiled brass spring "
            "terminals, evenly spaced like seedlings in a garden bed, with a few components set "
            "among them - a fat capacitor, a coil, a transformer, a round meter face. The lid "
            "stands open at the top of the frame, and a thick paper manual lies half on the counter "
            "beside it, open to a page of neat diagrams. Two small hands rest on the counter edge at "
            "the very bottom of the frame, nothing else of the child visible. Warm tungsten shop "
            "light, dust in the air, the counter's wood grain, a curl of solder wire."
        ),
    },
    # ---- s2: the 1970s Main Street, three parallax planes ------------------------------------
    "1970s-sky": {
        "kind": "layer",
        "beat": "s2",
        "transparent": False,
        "prompt": (
            "An empty daytime sky over a small American town, late morning: flat muted teal-blue "
            "with a few soft flat-shaded cream clouds, a low ridge of hills along the bottom "
            "quarter, and three thin telephone poles with sagging wires in the far distance. "
            "Nothing else in the frame. Wide, calm, mostly sky."
        ),
    },
    "1970s-shops": {
        "kind": "layer",
        "beat": "s2",
        "transparent": True,
        "prompt": (
            "A single continuous row of five 1970s strip-mall shopfronts, drawn straight on from "
            "across the street, filling the frame left to right and cut off at the bottom edge. "
            "Left to right: a pharmacy with a striped canvas awning; a small electronics hobby "
            "shop with a wood-panelled front, an orange awning and a glass door propped open on a "
            "scrap of plywood; an empty unit with brown paper taped inside the windows; a pizza "
            "counter; and a wide flat-roofed appliance-and-television store with televisions "
            "stacked in the window. Blank sign boards with no lettering on them at all. "
            "The row is isolated on a fully transparent background - no sky, no ground, no "
            "backdrop, nothing behind or around the buildings."
        ),
    },
    "1970s-foreground": {
        "kind": "layer",
        "beat": "s2",
        "transparent": True,
        "prompt": (
            "Foreground street clutter for the near side of a 1970s small-town street, arranged "
            "along the bottom third of a wide frame and cut off by the bottom edge: the rear half "
            "of a parked wood-panelled station wagon on the left, a fire hydrant, a bicycle "
            "leaning on its kickstand, a metal lamppost rising off the right edge, and a scatter "
            "of dry leaves on kerbstone. Drawn larger and heavier than mid-distance objects, as "
            "things close to the camera are. Isolated on a fully transparent background - no sky, "
            "no buildings, no ground plane behind them, nothing but the objects themselves."
        ),
    },
    # ---- s5: the same street, the 1990s -------------------------------------------------------
    "1990s-sky": {
        "kind": "layer",
        "beat": "s5",
        "transparent": False,
        "prompt": (
            "An empty early-evening sky over a small American town: flat dusty violet-blue fading "
            "to a band of muted orange along the horizon, two flat-shaded grey clouds, a low ridge "
            "of hills along the bottom quarter, telephone poles with sagging wires in the far "
            "distance. Nothing else in the frame. Wide, quiet, mostly sky."
        ),
    },
    "1990s-shops": {
        "kind": "layer",
        "beat": "s5",
        "transparent": True,
        "prompt": (
            "A single continuous row of five 1990s strip-mall shopfronts, drawn straight on from "
            "across the street, filling the frame left to right and cut off at the bottom edge. "
            "Left to right: a pharmacy; a small electronics shop whose window display is now "
            "pagers, phone cords and belt clips on pegboard; a video-rental unit with tall shelves "
            "visible inside; an arcade whose left half is lit and whose right half is completely "
            "dark; and a single-screen cinema with a projecting marquee whose panels are blank "
            "white boards ringed with round light bulbs, about half of the bulbs lit and half "
            "dark. No lettering anywhere, blank sign boards only. The row is isolated on a fully "
            "transparent background - no sky, no ground, no backdrop, nothing behind the "
            "buildings."
        ),
    },
    "1990s-foreground": {
        "kind": "layer",
        "beat": "s5",
        "transparent": True,
        "prompt": (
            "Foreground street clutter for the near side of a 1990s small-town street, arranged "
            "along the bottom third of a wide frame and cut off by the bottom edge: a boxy payphone "
            "on a post at the left, a squat newspaper vending box, a bike rack with one bicycle in "
            "it, a metal lamppost rising off the right edge, and a kerb with a storm drain. Drawn "
            "larger and heavier than mid-distance objects, as things close to the camera are. "
            "Isolated on a fully transparent background - no sky, no buildings, no ground plane "
            "behind them, nothing but the objects themselves."
        ),
    },
    # ---- s1, s4, s6: the three hero clips, and the stills they are animated from --------------
    "counter": {
        "kind": "clip",
        "beat": "s1",
        "still_prompt": (
            "Inside a small-town electronics hobby shop in 1974, seen over the shoulder of a boy "
            "of about nine who is standing at a wooden sales counter with his back to us, looking "
            "up. On the counter in front of him sits a closed hobby-kit box with a plywood frame "
            "and rows of small coiled spring terminals showing. Behind the counter: a wall of "
            "small parts drawers, coiled wire on hooks, a shopkeeper's shoulder and forearm at the "
            "edge of frame with his face out of shot. Warm tungsten light, dust in the air, "
            "wood-panelled walls."
        ),
        "motion_prompt": (
            "Slow, steady dolly in toward the kit box on the counter. The boy shifts his weight "
            "and leans in a little; the shopkeeper's hand moves a small part across the counter "
            "toward him. Dust drifts through the warm light. Locked-off, unhurried, no camera "
            "shake, no zoom snap, no text or captions appearing."
        ),
    },
    "saturday-door": {
        "kind": "clip",
        "beat": "s4",
        "still_prompt": (
            "Outside a 1980s strip mall on a bright Saturday mid-morning, drawn straight on from "
            "across the walkway. The electronics shop's glass door stands propped open on a scrap "
            "of plywood, and a kid of about ten is stepping out through it carrying a flat hobby-"
            "kit box under one arm, seen from behind and to the side with the face away from us. "
            "Next door, an arcade front with neon tubing and its doors open. Bunting, a bike "
            "against a post, hard morning shadows on the concrete walkway. Blank sign boards with "
            "no lettering."
        ),
        "motion_prompt": (
            "The kid steps out through the propped door and walks away along the walkway carrying "
            "the box, getting slightly smaller. The propped door sways a little. The arcade's neon "
            "tubes flicker faintly. Slow push in, steady weight, no camera shake, no text or "
            "captions appearing."
        ),
    },
    "shops-closing": {
        "kind": "clip",
        "beat": "s6",
        "still_prompt": (
            "The same small-town strip mall at dusk in the early 2000s, drawn straight on from "
            "across the walkway, four shopfronts in a row across the frame and all four still lit. "
            "Left to right: a mobile-phone store with a bare white-lit window where the "
            "wood-panelled electronics shop used to be; a video-rental store with half-empty "
            "shelves visible through the glass; an arcade with a half-raised metal roll shutter "
            "and a cabinet being wheeled out; and a big flat-roofed electronics store with sealed "
            "cartons stacked in the window. Blank sign boards with no lettering. Violet dusk sky, "
            "wet asphalt, an empty walkway."
        ),
        "motion_prompt": (
            "One at a time, left to right, each of the four shopfronts goes dark: the phone store's "
            "window light cuts out, then the video store's, then the arcade's metal roll shutter "
            "comes all the way down, then the big store's. The walkway is left lit only by the "
            "dusk sky. Locked-off wide shot, no camera move, no text or captions appearing."
        ),
    },
}


# ---------------------------------------------------------------------------------------------
# The People of Ohmsville (#92, film 2). Nine of its eleven pictures are the town film's, reused
# from the directory above; these are the two it needs that no film has made. Same STYLE preamble,
# same gpt-image-2 rails, same costs.md discipline - a separate table only because they belong in
# a different film's asset directory.
PEOPLE_ASSETS: dict[str, dict] = {
    "classroom-desks": {
        "kind": "still",
        "beat": "s1",
        # The teller's own place, and the standard's rule that it is the film's first picture. Also
        # its last: s19 plays the same still pulling out, which is the film's frame closing.
        "prompt": (
            "An empty small-town junior-high science classroom late on an autumn afternoon, seen "
            "from the doorway: four pupil desks pushed together into one square table at the back "
            "of the room, and on the middle of it a 1970s hobby-kit box lying open - varnished "
            "plywood frame, tidy rows of small coiled brass spring terminals, lid standing up. A "
            "loose stack of ruled paper sheets squared off on the nearest desk corner. Behind the "
            "table a big slate chalkboard wiped to a grey haze, a wooden teacher's desk to one "
            "side, a tall window with low sun coming in across the floor. Rows of ordinary desks "
            "in front, chairs up on two of them. No people in frame, no hands, no writing legible "
            "anywhere. Warm cream light on the pushed-together table, the rest of the room in "
            "quiet plywood-tan shadow, with generous empty space above the table."
        ),
    },
    "sign-in-sheets": {
        "kind": "still",
        "beat": "s2",
        # What the listener is holding in the first line. The rule against legible lettering is the
        # house STYLE's, and it is why the pencil marks read as marks rather than as names.
        "prompt": (
            "A close, near-overhead view of a small loose stack of old ruled paper sheets held in "
            "two hands over a desk, the top sheet tilted to the light: a hand-ruled column down "
            "the left margin and a column of short pencilled marks running down it, soft and grey "
            "and worn, the kind of list somebody kept for years. The sheets are foxed at the "
            "corners, one dog-eared, a rusted paper clip on the stack. A wooden desk edge and a "
            "stub of pencil below. Absolutely no legible letters, words, numbers or names "
            "anywhere - the pencil marks are marks, not writing. Warm cream paper against "
            "plywood-tan desk, one soft pool of afternoon light, deep charcoal shadow at the edges."
        ),
    },
}

FILMS: dict[str, dict[str, dict]] = {"ohmsville": ASSETS, "people-of-ohmsville": PEOPLE_ASSETS}


def spend_so_far() -> float:
    """Every dollar this script has already logged, read back off costs.md."""
    if not COSTS.is_file():
        return 0.0
    rows = re.findall(r"^\| [^|]+ \| [^|]+ \| \$([0-9.]+) \|", COSTS.read_text(), re.M)
    return round(sum(float(m) for m in rows), 4)


def log_cost(asset: str, tool: str, usd: float) -> None:
    if not COSTS.is_file():
        COSTS.parent.mkdir(parents=True, exist_ok=True)
        COSTS.write_text(
            "# Ohmsville town film (#92) - generation spend\n\n"
            "Budget: $%.2f. Every call this script makes is a row here.\n\n"
            "| asset | tool | cost | when |\n|---|---|---|---|\n" % BUDGET_USD
        )
    with COSTS.open("a") as f:
        f.write("| %s | %s | $%.4f | %s |\n" % (asset, tool, usd, time.strftime("%Y-%m-%d %H:%M")))


def guard(asset: str, tool: str, estimate: float) -> None:
    spent = spend_so_far()
    if spent + estimate > BUDGET_USD:
        raise SystemExit(
            "refusing %s via %s: $%.2f already spent + $%.2f estimated crosses the $%.2f budget"
            % (asset, tool, spent, estimate, BUDGET_USD)
        )
    print("  [$%.2f spent, $%.2f this call] %s -> %s" % (spent, estimate, asset, tool))


def write_prompt(name: str, text: str) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    (ART / ("%s.prompt.txt" % name)).write_text(text.rstrip() + "\n")


def gen_image(name: str, prompt: str, transparent: bool, out: Path) -> None:
    """One illustration.

    The opaque case goes through the registry's own `openai_image` tool, the way every other film's
    art was made. The transparent case does not: that tool's input_schema has no `background` key,
    and a parallax plane without alpha is not a plane - it is a rectangle sitting on top of the sky.
    Rather than widen a tool six other projects share, the alpha case calls the same model directly
    with background="transparent", and logs its cost against the same ledger at the same rate.
    """
    full = STYLE + prompt
    write_prompt(name, full)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not transparent:
        guard(name, "openai_image", 0.211)
        result = registry.get("openai_image").execute({
            "prompt": full, "size": SIZE, "quality": "high",
            "output_format": "png", "output_path": str(out),
        })
        if not result.success:
            raise RuntimeError("%s: %s" % (name, result.error))
        log_cost(name, "openai_image", result.cost_usd or 0.211)
    else:
        from openai import OpenAI
        guard(name, "openai_image(transparent)", 0.211)
        client = OpenAI()
        r = client.images.generate(
            model="gpt-image-2", prompt=full, size=SIZE, quality="high",
            background="transparent", output_format="png", n=1,
        )
        out.write_bytes(base64.b64decode(r.data[0].b64_json))
        log_cost(name, "openai_image(transparent)", 0.211)

    size = out.stat().st_size
    if size < 10_000:
        raise RuntimeError("%s: wrote %d bytes" % (name, size))
    print("  %s  %.0f KB" % (out.name, size / 1024))


def start_frame_data_uri(still: Path) -> str:
    """The start frame, inline in the request rather than by way of fal storage.

    `tools/video/_shared.upload_image_fal` - which seedance_video.py reaches for whenever it is
    handed an `image_path` - POSTs to https://rest.alpha.fal.ai/storage/upload/initiate, and that
    endpoint answers this key with 403. seedance_video.py prefers a caller-supplied `image_url`
    over uploading anything, and fal's model endpoints take a data URI there, so the frame goes in
    the request body and no storage is involved. Downscaled to 720p JPEG on the way: the model
    renders at 720p regardless, and a 3 MB PNG is 4 MB of base64 for no extra pixels.
    """
    from io import BytesIO
    from PIL import Image

    img = Image.open(still).convert("RGB")
    img = img.resize((1280, round(1280 * img.height / img.width)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def gen_clip(name: str, spec: dict) -> None:
    """A hero beat: a still first, then five seconds of motion out of it."""
    still = ART / ("%s-frame.png" % name)
    if not still.is_file():
        gen_image("%s-frame" % name, spec["still_prompt"], False, still)

    out = ART / ("%s.mp4" % name)
    prompt = STYLE + spec["motion_prompt"]
    write_prompt(name, prompt)
    tool = registry.get("veo_video")
    inputs = {
        "prompt": prompt,
        "backend": "google",
        "operation": "image_to_video",
        # Google's backend reads the file and sends the bytes through the SDK, so no storage
        # bucket is involved - which is what rules Seedance out on this key (see this module's
        # own note above).
        "image_path": str(still),
        "duration": "8s",
        "aspect_ratio": "16:9",
        "resolution": "1080p",
        # No `generate_audio` key: the Gemini Developer API rejects it outright ("only supported
        # in Gemini Enterprise Agent Platform mode"), so Veo generates a soundtrack whether or not
        # this film wants one. It does not - there is narration and a bed already - and
        # build_trailer.py's loop_clip drops the audio stream with -an when it stages the file.
        "output_path": str(out),
    }
    guard(name, "veo_video", tool.estimate_cost(inputs))
    result = tool.execute(inputs)
    if not result.success:
        raise RuntimeError("%s: %s" % (name, result.error))
    log_cost(name, "veo_video", result.cost_usd or tool.estimate_cost(inputs))
    size = out.stat().st_size
    if size < 50_000:
        raise RuntimeError("%s: wrote %d bytes" % (name, size))
    print("  %s  %.1f MB" % (out.name, size / 1024 / 1024))


def build(name: str) -> None:
    spec = ASSETS[name]
    print("%s (%s, %s):" % (name, spec["beat"], spec["kind"]))
    if spec["kind"] == "clip":
        gen_clip(name, spec)
    else:
        gen_image(name, spec["prompt"], spec.get("transparent", False), ART / ("%s.png" % name))


def main() -> None:
    # Declared up here because --film's own default reads FILM below; Python requires the
    # declaration to precede every use of the name in the function.
    global FILM, ART, COSTS, ASSETS
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("names", nargs="*", help="asset names to (re)generate")
    ap.add_argument("--all", action="store_true", help="every asset that does not exist yet")
    ap.add_argument("--force", action="store_true", help="with --all, regenerate existing ones too")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--film", default=FILM, choices=sorted(FILMS),
                    help="which film's asset directory and table to work in (default: %(default)s)")
    args = ap.parse_args()

    # Rebound before any of the helpers below run, so ART, COSTS and ASSETS all name the same film
    # and a budget guard can never be read off one film's ledger while writing into another's.
    FILM = args.film
    ART = PROJECT / "assets" / "art" / FILM
    COSTS = ART / "costs.md"
    ASSETS = FILMS[FILM]

    if args.list:
        for n, s in ASSETS.items():
            ext = "mp4" if s["kind"] == "clip" else "png"
            have = (ART / ("%s.%s" % (n, ext))).is_file()
            print("  %-20s %-4s %-6s %s" % (n, s["beat"], s["kind"], "have" if have else "-"))
        print("\n  $%.2f of $%.2f spent" % (spend_so_far(), BUDGET_USD))
        return

    names = args.names or (list(ASSETS) if args.all else [])
    if not names:
        ap.error("name an asset, or pass --all / --list")
    for n in names:
        if n not in ASSETS:
            raise SystemExit("no such asset %r - %s" % (n, ", ".join(ASSETS)))
        ext = "mp4" if ASSETS[n]["kind"] == "clip" else "png"
        if args.all and not args.force and (ART / ("%s.%s" % (n, ext))).is_file():
            print("%s: already made, skipping" % n)
            continue
        build(n)
    print("\n$%.2f of $%.2f spent" % (spend_so_far(), BUDGET_USD))


if __name__ == "__main__":
    main()
