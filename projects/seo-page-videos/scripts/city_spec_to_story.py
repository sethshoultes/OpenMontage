"""Turn a short city spec into the story and voice files the page-video builder reads.

Usage: city_spec_to_story.py <spec.json>
spec: {name, page, title, arc, endcard{kicker,site,path,sub}, beats[{vo, pace, pause, kinetic[[text, anchor(, delay, hold)]],
       shots[[still(, anchor)]], to_next}]}
Writes stories/<name>.json and stories/<name>.vo.json (ids b01../s01..). Camera: a slow push-in on every shot.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
TO_NEXT = ["push-left", "push-right", "wipe-up", "slide-left", "wipe-right", "circle-open"]


def main(spec_path):
    sp = json.load(open(spec_path))
    beats, vo = [], []
    for i, b in enumerate(sp["beats"], 1):
        shots = []
        for s in b["shots"]:
            sh = {"still": s[0], "cam": [[0, 1.0, 0.5, 0.5], [1, 1.08, 0.5, 0.5]]}
            if len(s) > 1:
                sh["at"] = s[1]
            if s[0].startswith("proc:"):
                sh = {"still": s[0], "at": s[1]}
            shots.append(sh)
        beat = {"id": f"b{i:02d}", "vo": b["vo"], "to_next": b.get("to_next", TO_NEXT[i % len(TO_NEXT)]),
                "kinetic": b["kinetic"], "shots": shots}
        if b.get("pause") is not None:
            beat["pause"] = b["pause"]
        beats.append(beat)
        vo.append({"id": f"s{i:02d}", "vo": b["vo"], "pace": b.get("pace", 0.94)})
    story = {"page": sp["page"], "title": sp["title"], "arc": sp.get("arc", ""),
             "style": "Flat editorial vector, hard edges, flat solid ground, art centered ~70% width, nothing touching an edge; no glow, haze, gradients, soft shadows; no people, no logos.",
             "phrase_lead": 0.35, "srt_lead": 0.25, "caption_max": 3.6, "endcard": sp["endcard"], "beats": beats}
    json.dump(story, open(HERE / "stories" / f"{sp['name']}.json", "w"), indent=1)
    json.dump({"shots": vo}, open(HERE / "stories" / f"{sp['name']}.vo.json", "w"), indent=1)
    print("ok", sp["name"], len(beats), "beats")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
