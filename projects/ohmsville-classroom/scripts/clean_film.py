#!/usr/bin/env python3
"""Delete an Ohmsville film's scratch once its final is verified (caseproofagent/memberpress-ai-cast#166).

The last step of a film, after check_render.py passes and Seth approves the cut: the build's copies
go, so they don't pile up on the Mac. The same rule as memberpress-ai-cast's scripts/clean_scenes.py.

    .venv/bin/python projects/ohmsville-classroom/scripts/clean_film.py percepto [--dry-run]

Deleted, for a lesson (artifacts/<id>) or a trailer (artifacts/trailer-<id>):
  - the shot clips and stills in artifacts/.../_source_snapshot (its .json files stay, so
    check_render.py can still read the shot list),
  - the staged copies in remotion-composer/public/ohmsville/<id> or ohmsville-trailers/<id>
    (build_lesson.py and build_trailer.py stage them again on the next render),
  - renders/<id>/.final_review_frames.
Kept: renders/<id>/final.mp4, its captions, upload doc, and everything else in artifacts/.

The final is verified first with ffprobe (a video stream, longer than a second). If it fails,
nothing is deleted and the exit code is 1.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects" / "ohmsville-classroom"
PUBLIC = ROOT / "remotion-composer" / "public"


def verified(final: Path) -> bool:
    if not final.is_file() or final.stat().st_size == 0:
        return False
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", str(final)], capture_output=True, text=True)
    if out.returncode != 0:
        return False
    info = json.loads(out.stdout)
    video = any(s.get("codec_type") == "video" for s in info.get("streams", []))
    return video and float(info.get("format", {}).get("duration", 0)) > 1


def size(p: Path) -> int:
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def scratch(film: str) -> list[Path]:
    paths = []
    for art in (PROJECT / "artifacts" / film, PROJECT / "artifacts" / f"trailer-{film}"):
        shots = art / "_source_snapshot"
        if shots.is_dir():
            paths += [p for p in shots.iterdir() if p.suffix != ".json"]
    paths += [PUBLIC / "ohmsville" / film, PUBLIC / "ohmsville-trailers" / film,
              PROJECT / "renders" / film / ".final_review_frames"]
    return [p for p in paths if p.exists()]


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    if len(args) != 1:
        sys.exit(__doc__)
    film = args[0]
    final = PROJECT / "renders" / film / "final.mp4"
    if not verified(final):
        print(f"clean_film: {final} is not a verified video; nothing deleted")
        return 1
    freed = 0
    for p in scratch(film):
        freed += size(p)
        print(f"{'would delete' if dry_run else 'deleted'} {p}")
        if not dry_run:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    print(f"clean_film: {film}: {freed / 1e6:.0f} MB {'to free' if dry_run else 'freed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
