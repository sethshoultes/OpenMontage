#!/usr/bin/env python3
"""Generate one inventor trailer's still illustrations (art:/anim: model, docs/video-guidelines.md).

    python projects/ohmsville-classroom/scripts/gen_inventor_assets.py --list lewis-latimer
    python projects/ohmsville-classroom/scripts/gen_inventor_assets.py lewis-latimer s2-the-office-boy
    python projects/ohmsville-classroom/scripts/gen_inventor_assets.py --all lewis-latimer

Each inventor film's `art:` beats (history/biography sections with no board demo) get one
full-bleed illustration each, in the same vintage-engraving look already established for Volta,
Ohm and Faraday (`assets/art/inventor-*/`): warm sepia, period detail, no text/logos/brand names,
faces turned away or in profile rather than a straight camera-facing portrait.

Every asset writes its prompt next to itself as `<name>.prompt.txt` and every call appends to
`costs.md` in the same per-inventor directory. BUDGET_USD is a hard stop per film, matching the
$1.50/film illustration budget from the team's standing instructions — four stills at $0.211 each
is $0.844, comfortably inside it.

ASSETS below covers Lewis Latimer (inventor-lewis-latimer). Add the next inventor's dict alongside
it to reuse this script rather than writing a fresh one-off each time.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"

BUDGET_USD = 1.50
SIZE = "1536x1024"

sys.path.insert(0, str(ROOT))
from tools.tool_registry import registry  # noqa: E402

registry.discover()

# The house look for inventor-film stills: vintage sepia illustration, period-accurate, no text.
STYLE = (
    "Vintage sepia-toned editorial illustration in the style of a 19th-century engraving or oil "
    "study: warm candlelight or window light, fine linework, soft painterly shading, period-accurate "
    "clothing, furniture and instruments for the decade shown. "
    "Absolutely no text, no letters, no numbers, no signage lettering, no logos, no brand names, "
    "no diagrams with labels. No recognizable real person's face rendered as a straight-on portrait: "
    "show the figure from behind, in profile, in silhouette, or with the face turned away or in "
    "shadow. No modern objects, no photographic realism, no 3D render. "
)

INVENTORS: dict[str, dict] = {
    "lewis-latimer": {
        "assets": {
            "s1-the-bulb": (
                "A single incandescent lamp with a long fragile carbon filament, sitting alone on a "
                "wooden workbench in cold, pale early-morning light through a window, its filament "
                "gone dark and slightly broken - clearly burnt out overnight. Beside it, in shadow, "
                "the faint impression of last night's warm glow still visible in the room's leftover "
                "candle stubs and an open notebook. A quiet, puzzled morning stillness."
            ),
            "s2-the-office-boy": (
                "An 1870s patent law office at dusk, lit by a single oil lamp: a young Black draftsman "
                "seen from behind or in side silhouette, bent over a drafting table covered in "
                "technical line drawings and a large brass compass, ink bottles and rulers at hand. "
                "Tall shelves of bound patent volumes behind him. Warm lamp light on the paper, the "
                "rest of the room in soft shadow."
            ),
            "s3-the-patent": (
                "A small electric lamp workshop in the early 1880s: a workbench crowded with glass "
                "bulb blanks, spools of thin carbon filament, a small hand-cranked vacuum pump, and "
                "a stack of patent papers weighted down by a pair of pliers. One finished bulb glows "
                "faintly on the bench, its filament long and looping. Figure working at the bench "
                "seen from behind or in profile, sleeves rolled up, warm gaslight."
            ),
            "s4-the-name-everybody-remembers": (
                "A writer's desk at night in a book-lined study: an open manuscript titled with no "
                "visible words, a steady incandescent desk lamp burning warm and even beside it, and "
                "through a tall window behind the desk, a distant nighttime city skyline dotted with "
                "small lit windows. A figure seated at the desk, pen in hand, seen from behind or in "
                "silhouette against the window light."
            ),
        },
    },
}


def art_dir(slug: str) -> Path:
    return PROJECT / "assets" / "art" / ("inventor-%s" % slug)


def costs_file(slug: str) -> Path:
    return art_dir(slug) / "costs.md"


def spend_so_far(slug: str) -> float:
    costs = costs_file(slug)
    if not costs.is_file():
        return 0.0
    rows = re.findall(r"^\| [^|]+ \| [^|]+ \| \$([0-9.]+) \|", costs.read_text(), re.M)
    return round(sum(float(m) for m in rows), 4)


def log_cost(slug: str, asset: str, tool: str, usd: float) -> None:
    costs = costs_file(slug)
    if not costs.is_file():
        costs.parent.mkdir(parents=True, exist_ok=True)
        costs.write_text(
            "# inventor-%s illustrations - generation spend\n\n"
            "Budget: $%.2f/film. Every call this script makes is a row here.\n\n"
            "| asset | tool | cost | when |\n|---|---|---|---|\n" % (slug, BUDGET_USD)
        )
    with costs.open("a") as f:
        f.write("| %s | %s | $%.4f | %s |\n" % (asset, tool, usd, time.strftime("%Y-%m-%d %H:%M")))


def guard(slug: str, asset: str, tool: str, estimate: float) -> None:
    spent = spend_so_far(slug)
    if spent + estimate > BUDGET_USD:
        raise SystemExit(
            "refusing %s via %s: $%.2f already spent + $%.2f estimated crosses the $%.2f/film budget"
            % (asset, tool, spent, estimate, BUDGET_USD)
        )
    print("  [$%.2f spent, $%.2f this call] %s -> %s" % (spent, estimate, asset, tool))


def write_prompt(slug: str, name: str, text: str) -> None:
    d = art_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s.prompt.txt" % name)).write_text(text.rstrip() + "\n")


def gen_image(slug: str, name: str, prompt: str) -> None:
    full = STYLE + prompt
    write_prompt(slug, name, full)
    out = art_dir(slug) / ("%s.png" % name)
    out.parent.mkdir(parents=True, exist_ok=True)

    guard(slug, name, "openai_image", 0.211)
    result = registry.get("openai_image").execute({
        "prompt": full, "size": SIZE, "quality": "high",
        "output_format": "png", "output_path": str(out),
    })
    if not result.success:
        raise RuntimeError("%s: %s" % (name, result.error))
    log_cost(slug, name, "openai_image", result.cost_usd or 0.211)

    size = out.stat().st_size
    if size < 10_000:
        raise RuntimeError("%s: suspiciously small output (%d bytes)" % (name, size))
    print("  -> %s (%.1f KB)" % (out, size / 1024))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="inventor slug, e.g. lewis-latimer")
    ap.add_argument("names", nargs="*", help="specific asset names, else --all")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.slug not in INVENTORS:
        raise SystemExit("no ASSETS entry for %r — add one to gen_inventor_assets.py" % args.slug)
    assets = INVENTORS[args.slug]["assets"]

    if args.list:
        for name in assets:
            print(name)
        return

    names = list(assets) if args.all else args.names
    if not names:
        raise SystemExit("pass asset names, --all, or --list")

    for name in names:
        if name not in assets:
            raise SystemExit("no such asset %r for %s (--list to see names)" % (name, args.slug))
        print("generating %s/%s..." % (args.slug, name))
        gen_image(args.slug, name, assets[name])


if __name__ == "__main__":
    main()
