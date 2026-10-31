"""YouTube upload pack for one page video: title, description (with the page link and chapters), tags, chapters and the SRT.

Usage: make_youtube_pack.py <story-name> <video.mp4> <page-text.txt> <out-dir>
Reads stories/<story-name>.json (title, page URL, beats, kinetic captions), <video>.timeline.json (beat times) and <video>.srt.
Chapters: the first beat at 0:00, then a new chapter at each beat that starts 10 s or more after the last one (YouTube needs 3+ chapters,
each 10 s or longer); a chapter is named by the first caption of its beat. Nothing is uploaded: the pack is for Seth's sethshoultes channel.
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent


def stamp(t):
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


def main(name, video, page_txt, out):
    video, out = Path(video), Path(out)
    story = json.load(open(HERE / "stories" / f"{name}.json"))
    tl = json.load(open(video.with_suffix(".timeline.json")))
    page = [l for l in Path(page_txt).read_text().splitlines() if l.strip()]
    url = story["page"]
    title = story["title"]
    hero = page[3] if len(page) > 3 else ""
    beats = {b["id"]: b for b in story["beats"]}
    chapters, last = [], None
    for b in tl["beats"]:
        start = 0.0 if not chapters else b["start"]
        if not chapters or start - last >= 10:
            cap = beats[b["id"]]["kinetic"][0][0].strip(" .?!").lower()
            cap = cap[0].upper() + cap[1:]
            chapters.append((start, cap))
            last = start
    if chapters[0][1].lower() == "quick question":
        chapters[0] = (0.0, "The question")
    assert len(chapters) >= 3, "YouTube needs at least 3 chapters"
    card = story["endcard"]
    desc = (f"{hero}\n\nThe page: {url}\n\nChapters\n" + "\n".join(f"{stamp(t)} {c}" for t, c in chapters) +
            f"\n\nSeth Shoultes: {card['kicker']}. Book a call: {url}\nsethshoultes.com")
    tags = sorted({w for w in [title, "Seth Shoultes", "Southern Utah", "St. George Utah", card["kicker"]] if w})
    out.mkdir(parents=True, exist_ok=True)
    (out / "title.txt").write_text(f"{title} | Seth Shoultes\n")
    (out / "description.txt").write_text(desc + "\n")
    (out / "tags.txt").write_text(", ".join(tags) + "\n")
    (out / "chapters.txt").write_text("\n".join(f"{stamp(t)} {c}" for t, c in chapters) + "\n")
    shutil.copy(video.with_suffix(".srt"), out / "captions.srt")
    (out / "README.txt").write_text(
        f"Video file: {video}\nUpload to Seth's sethshoultes channel only (never the Opal channel); his channel is not signed in to a browser we drive yet.\n"
        "Captions: upload captions.srt as the English caption track.\n"
        "Altered-or-synthetic disclosure: the narration is Seth's own ElevenLabs voice clone; decide the YouTube disclosure flag at upload (no AI label goes in the description).\n")
    print("ok", out, f"{len(chapters)} chapters")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
