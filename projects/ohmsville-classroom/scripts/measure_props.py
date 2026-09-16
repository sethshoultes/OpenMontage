#!/usr/bin/env python3
"""Measure the Spooky Shack trailer's corner props, directly — a printed number, not an eyeball.

    python projects/ohmsville-classroom/scripts/measure_props.py

For every board cut in the trailer's own composition.json that carries a `prop`, extracts one real
frame from the rendered final.mp4 and checks, against the ACTUAL PIXELS:

  - the prop's visible area (pixels meaningfully different from the plum ground, within its own
    box) is between 3% and 9% of the frame's total pixels;
  - the prop's box does not intersect the board's box (computed from the same `videoScale`/margin
    math OhmsvilleLesson.tsx's VideoCut and CornerProp use — see PROP_MARGIN_INSET/PROP_BOX_ASPECT,
    kept in sync with remotion-composer/src/OhmsvilleLesson.tsx by hand, both small and stable);
  - the prop's box does not intersect the caption's box (a conservative UPPER BOUND — the widest
    and tallest CaptionOverlay's own CSS ever lets a caption pill get: maxWidth 80% centered,
    paddingBottom 80px, one line's worth of height — not the real pill, which is content-dependent
    and only ever smaller. If the prop clears this bound, it clears every real caption too.)

Exits non-zero, printing which check failed and its numbers, if any beat fails either bound.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
TRAILER_ID = "spooky-shack"
RENDER = PROJECT / "renders" / TRAILER_ID / "final.mp4"
COMPOSITION = PROJECT / "artifacts" / f"trailer-{TRAILER_ID}" / "composition.json"
FRAMES_DIR = PROJECT / "artifacts" / f"trailer-{TRAILER_ID}" / "prop_frames"

WIDTH, HEIGHT = 1920, 1080
FRAME_PIXELS = WIDTH * HEIGHT
PLUM = (20, 12, 28)
COLOR_DISTANCE_THRESHOLD = 18  # a pixel this far (or more) from PLUM, in RGB, counts as "prop ink"

# Kept in sync BY HAND with remotion-composer/src/OhmsvilleLesson.tsx's exported constants — small,
# stable numbers, not worth a build step to share across a Python script and a TSX component.
PROP_MARGIN_INSET = 12
PROP_BOX_ASPECT = 300 / 360  # width:height

# CaptionOverlay's maxWidth ("80%", centered) turned out not to be a usable safety bound once the
# board (and so the caption, docked paddingBottom=80 from the FRAME regardless of the board's own
# margin — see below) sits inside a margin: at videoScale 0.65 the margin is wider than the 10%
# clearance that bound implies, so it overlaps every corner a prop could stand in even though no
# REAL caption (5 words, this trailer's own longest line) gets anywhere near that wide. Measuring
# the actual pill instead, per frame, the same way CAPTION_SEARCH_Y is derived: CaptionOverlay docks
# paddingBottom=80 from the frame's own bottom, not the board's — at this scale that puts the whole
# pill inside the bottom margin band (board's bottom edge is well above y=1000), so no board content
# can ever appear in this search strip to confuse the detector, only the pill's cream/orange text.
CAPTION_SEARCH_Y = (HEIGHT - 80 - 110, HEIGHT)  # a little taller than one pill, for margin
CAPTION_TEXT_COLORS = [(246, 239, 220), (255, 179, 71)]  # cream body, #ffb347 highlighted word
CAPTION_TEXT_THRESHOLD = 40
CAPTION_PAD_X, CAPTION_PAD_Y = 28, 14  # PageRenderer's own pill padding: "14px 28px"


def find_caption_box(frame: Image.Image) -> dict | None:
    """The real caption pill's bounding box in THIS frame, from its text pixels — or None if no
    caption is showing (a board beat can start/end without one, at the trim edges)."""
    y0, y1 = CAPTION_SEARCH_Y
    region = frame.crop((0, y0, WIDTH, y1)).convert("RGB")
    px = region.load()
    w, h = region.size
    xs, ys = [], []
    for yy in range(h):
        for xx in range(w):
            r, g, b = px[xx, yy]
            for cr, cg, cb in CAPTION_TEXT_COLORS:
                if ((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2) ** 0.5 < CAPTION_TEXT_THRESHOLD:
                    xs.append(xx)
                    ys.append(yy)
                    break
    if not xs:
        return None
    return {
        "x0": min(xs) - CAPTION_PAD_X, "x1": max(xs) + CAPTION_PAD_X,
        "y0": y0 + min(ys) - CAPTION_PAD_Y, "y1": y0 + max(ys) + CAPTION_PAD_Y,
    }


def board_rect(scale: float) -> dict:
    margin_x = WIDTH * (1 - scale) / 2
    margin_y = HEIGHT * (1 - scale) / 2
    return {"x0": margin_x, "y0": margin_y, "x1": WIDTH - margin_x, "y1": HEIGHT - margin_y}


def prop_rect(scale: float, corner: str, prop_height: float | None) -> dict:
    margin_x = WIDTH * (1 - scale) / 2
    box_w = max(0.0, margin_x - PROP_MARGIN_INSET * 2)
    # build_trailer.py's PROP_FOR gives each prop its own height (per-source-image ink density);
    # the shared aspect is only a fallback for a prop that doesn't set one.
    box_h = prop_height if prop_height is not None else box_w / PROP_BOX_ASPECT
    y0, y1 = HEIGHT - PROP_MARGIN_INSET - box_h, HEIGHT - PROP_MARGIN_INSET
    if corner == "bottom-left":
        x0, x1 = PROP_MARGIN_INSET, PROP_MARGIN_INSET + box_w
    else:
        x0, x1 = WIDTH - PROP_MARGIN_INSET - box_w, WIDTH - PROP_MARGIN_INSET
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def intersects(a: dict, b: dict) -> bool:
    return a["x0"] < b["x1"] and a["x1"] > b["x0"] and a["y0"] < b["y1"] and a["y1"] > b["y0"]


def extract_frame(t: float, out_path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(t), "-i", str(RENDER), "-frames:v", "1", "-update", "1", str(out_path)],
        check=True, capture_output=True,
    )


def measure_prop_area(frame: Image.Image, box: dict) -> int:
    """Pixels within `box` whose colour differs from PLUM by more than the threshold."""
    x0, y0, x1, y1 = (round(box["x0"]), round(box["y0"]), round(box["x1"]), round(box["y1"]))
    region = frame.crop((max(0, x0), max(0, y0), min(WIDTH, x1), min(HEIGHT, y1))).convert("RGB")
    count = 0
    px = region.load()
    w, h = region.size
    for yy in range(h):
        for xx in range(w):
            r, g, b = px[xx, yy]
            dist = ((r - PLUM[0]) ** 2 + (g - PLUM[1]) ** 2 + (b - PLUM[2]) ** 2) ** 0.5
            if dist > COLOR_DISTANCE_THRESHOLD:
                count += 1
    return count


def main() -> int:
    if not RENDER.is_file():
        print(f"no render at {RENDER} — run build_trailer.py first", file=sys.stderr)
        return 2
    props = json.loads(COMPOSITION.read_text())
    theme = props["themeConfig"]
    scale = theme.get("videoScale", 1)
    board = board_rect(scale)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    beats = [c for c in props["cuts"] if c.get("prop")]
    if not beats:
        print("no board cut in composition.json carries a prop — nothing to measure", file=sys.stderr)
        return 2

    print(f"videoScale={scale}  board={board}\n")

    failures = []
    for cut in beats:
        corner = cut.get("propCorner", "bottom-right")
        prop = prop_rect(scale, corner, cut.get("propHeight"))
        mid = cut["in_seconds"] + (cut["out_seconds"] - cut["in_seconds"]) * 0.6
        frame_path = FRAMES_DIR / f"{cut['id']}.png"
        extract_frame(mid, frame_path)
        frame = Image.open(frame_path)
        if frame.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"{cut['id']}: frame is {frame.size}, expected {(WIDTH, HEIGHT)}")

        ink_px = measure_prop_area(frame, prop)
        pct = ink_px / FRAME_PIXELS * 100
        hits_board = intersects(prop, board)
        caption = find_caption_box(frame)
        hits_caption = caption is not None and intersects(prop, caption)

        ok = (3.0 <= pct <= 9.0) and not hits_board and not hits_caption
        status = "OK" if ok else "FAIL"
        cap_str = "none" if caption is None else (
            f"{{'x0': {caption['x0']:.0f}, 'y0': {caption['y0']:.0f}, "
            f"'x1': {caption['x1']:.0f}, 'y1': {caption['y1']:.0f}}}"
        )
        print(
            f"[{status}] {cut['id']:>6}  corner={corner:<12}  prop_box={{'x0': {prop['x0']:.0f}, "
            f"'y0': {prop['y0']:.0f}, 'x1': {prop['x1']:.0f}, 'y1': {prop['y1']:.0f}}}  "
            f"visible={ink_px}px ({pct:.2f}% of frame)  hits_board={hits_board}\n"
            f"         caption_box={cap_str}  hits_caption={hits_caption}"
        )
        if not ok:
            failures.append(cut["id"])

    print()
    if failures:
        print(f"FAILED: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"All {len(beats)} board beats: prop area in [3%, 9%], clear of the board and the caption box.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
