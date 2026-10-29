"""Three takes per line in Seth's ElevenLabs clone, ranked for liveliness, with character timings for the kinetic type.

Usage: gen_vo.py <story.json> <out-dir>
Env:   ELEVENLABS_API_KEY
Why Multilingual v2: on Seth's clone, Eleven v3 and v4 render the voice about 6 semitones higher (median F0 about 190-205 Hz
against his 130 Hz), which does not sound like him; Multilingual v2 holds 128-132 Hz. A take is only eligible if its median
F0 is within 12% of REF_F0. Among eligible takes the liveliest is picked: pitch spread plus pitch range. The audio tags in
the story file are stripped (v2 would read them aloud). Pace is per line: slower on the key point, faster through lists.
"""
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vo_metrics import metrics  # noqa: E402

CFG = json.load(open(Path(__file__).parent / "config.json"))
REF_F0 = 130.0
TAKES = [  # (stability, style, speed offset)
    (0.30, 0.50, 0.0), (0.35, 0.45, 0.04), (0.40, 0.40, -0.03)]
KEY = {"s03": 0.93, "s04": 0.95, "s11": 0.92, "s13": 0.95}   # slow down on the points that land
LIST = {"s07": 1.06, "s08": 1.06, "s09": 1.02}                # speed up through the lists


def tts(text, out, stability, style, speed):
    body = {"text": text, "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": stability, "similarity_boost": 0.9, "style": style, "use_speaker_boost": True, "speed": speed}}
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{CFG['voice_id']}/with-timestamps?output_format=mp3_44100_128",
        json.dumps(body).encode(), {"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=180))
    Path(str(out) + ".mp3").write_bytes(base64.b64decode(r["audio_base64"]))
    json.dump(r["alignment"], open(str(out) + ".json", "w"))


def main(story, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    picked = {}
    for s in json.load(open(story))["shots"]:
        text = re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", s["vo"])).strip()
        base = s.get("pace", KEY.get(s["id"], LIST.get(s["id"], 1.0)))  # a story can set its own pace per line
        rows = []
        for n, (stab, style, off) in enumerate(TAKES, 1):
            p = out / f"{s['id']}-t{n}"
            if not Path(str(p) + ".mp3").exists():
                tts(text, p, stab, style, round(min(1.2, max(0.7, base + off)), 2))
            m = metrics(str(p) + ".mp3")
            ok = abs(m["f0_med"] - REF_F0) / REF_F0 <= 0.12
            rows.append((m["spread_st"] + 0.35 * m["range_p10_p90_st"] if ok else -1, n, m))
            print(s["id"], f"t{n}", m, "eligible" if ok else "OFF-VOICE")
        best = max(rows)
        if best[0] < 0:
            sys.exit(f"{s['id']}: no take within 12% of {REF_F0} Hz")
        picked[s["id"]] = {"take": best[1], "file": f"{s['id']}-t{best[1]}.mp3", "metrics": best[2]}
    json.dump(picked, open(out / "picked.json", "w"), indent=1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
