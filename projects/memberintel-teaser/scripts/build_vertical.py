"""Build + render the 30s MembersIntel teaser — 9:16 VERTICAL variant."""
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-teaser"
PARENT_IMG = P / "assets/images"
PUBDIR = ROOT / "remotion-composer/public/mi-brains"

BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"
PUB = lambda n: f"mi-brains/{n}"

# Stage teaser frames into public/
for f in ["v-frame-b-typed.png", "v-frame-c-sent.png", "v-frame-d-stream.png", "v-frame-e-masked.png"]:
    subprocess.run(["cp", str(PARENT_IMG / f), str(PUBDIR / f)], check=True)

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

SECTIONS = ["t1", "t2", "t3", "t4"]
D = {s: dur(P / f"assets/narration/{s}.mp3") for s in SECTIONS}
LEAD = 1.2; GAP = 0.5; TAIL = 3.0
NARR = {}
t = LEAD
for s in SECTIONS:
    NARR[s] = round(t, 2)
    t += D[s] + GAP
TOTAL = round(t - GAP + TAIL, 2)

def win(s):
    i = SECTIONS.index(s)
    start = 0.0 if i == 0 else NARR[s]
    end = TOTAL if i == len(SECTIONS) - 1 else NARR[SECTIONS[i + 1]]
    return start, end

w1 = win("t1"); w2 = win("t2"); w3 = win("t3"); w4 = win("t4")
m2 = round(w2[0] + (w2[1] - w2[0]) * 0.62, 2)
m3 = round(w3[0] + (w3[1] - w3[0]) * 0.5, 2)

CUTS = [
    ("cut-1", "anime_scene", *w1, {"images": [PUB("v-frame-b-typed.png"), PUB("v-frame-c-sent.png")], "animation": "zoom-in", "vignette": False},
     {"source": "", "reason": "typing -> sent, real capture"}),
    ("cut-2a", "anime_scene", w2[0], m2, {"images": [PUB("v-frame-d-stream.png"), PUB("v-frame-e-masked.png")], "animation": "zoom-in", "vignette": False},
     {"source": "", "reason": "streaming -> full answer (masked)"}),
    ("cut-2b", None, m2, w2[1], {}, {"source": PUB("v-shelves.png"), "transform": {"animation": "ken-burns"}, "reason": "playbook library flash"}),
    ("cut-3a", None, w3[0], m3, {}, {"source": PUB("v-split.png"), "transform": {"animation": "zoom-in"}, "reason": "two brains"}),
    ("cut-3b", None, m3, w3[1], {}, {"source": PUB("v-flywheel.png"), "transform": {"animation": "zoom-in"}, "reason": "flywheel flash"}),
    ("cut-4", None, *w4, {}, {"source": PUB("v-logo-card.png"), "transform": {"animation": "static"}, "reason": "logo end card"}),
]

THEME = {
    "primaryColor": TEAL, "accentColor": "#F97316", "backgroundColor": BG,
    "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
    "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
    "chartColors": [TEAL, NAVY, "#F97316"],
    "springConfig": {"damping": 18, "stiffness": 170, "mass": 1},
    "transitionDuration": 0.3,
    "captionHighlightColor": TEAL, "captionTextColor": NAVY,
    "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
}

# narration_full
inputs = []; filters = []
for i, s in enumerate(SECTIONS):
    inputs += ["-i", str(P / f"assets/narration/{s}.mp3")]
    ms = int(NARR[s] * 1000)
    filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(SECTIONS)))
fc = ";".join(filters) + f";{mix}amix=inputs={len(SECTIONS)}:normalize=0,apad=whole_dur={TOTAL}[out]"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2", str(P / "assets/narration/narration_full.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/narration/narration_full.mp3"), str(PUBDIR / "teaser_narration.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/music/background_music.mp3"), str(PUBDIR / "teaser_music.mp3")], check=True)
print(f"narration assembled: {TOTAL}s | " + ", ".join(f"{s}@{NARR[s]}" for s in SECTIONS))

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(P / "assets/narration/narration_full.mp3"), word_timestamps=True, language="en")
captions = []
for seg in segments:
    for w in seg.words or []:
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})
json.dump(captions, open(P / "artifacts/captions.json", "w"), indent=1)
print(len(captions), "caption words")

artifact_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "source": art["source"], "in_seconds": tin, "out_seconds": tout,
           "layer": "primary", "transition_in": "fade", "transition_out": "fade",
           "transition_duration": 0.3, "reason": art["reason"]}
    if "transform" in art:
        cut["transform"] = art["transform"]
    artifact_cuts.append(cut)
artifact = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": artifact_cuts,
    "audio": {
        "narration": {"segments": [{"asset_id": f"narration-{s}", "start_seconds": NARR[s]} for s in SECTIONS]},
        "music": {"asset_id": "music-bg", "volume": 0.16, "fade_in_seconds": 0.5, "fade_out_seconds": 1.5,
                  "ducking": {"enabled": True, "reduction_db": -6}},
    },
    "subtitles": {"enabled": True, "style": "word-by-word", "source": "artifacts/captions.json",
                  "font": "Inter", "position": "bottom-center"},
    "metadata": {"project_id": "memberintel-teaser", "playbook": "custom-membersintel-brand",
                 "target_duration_seconds": TOTAL,
                 "notes": "9:16 vertical variant; real mobile-UI captures (masked per Q2); vertical brand graphics."},
}
jsonschema.validate(artifact, json.load(open(ROOT / "schemas/artifacts/edit_decisions.schema.json")))
json.dump(artifact, open(P / "artifacts/edit_decisions.json", "w"), indent=2)
print("edit_decisions: VALID")

comp_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "in_seconds": tin, "out_seconds": tout, "transition_in": "fade", "transition_out": "fade"}
    if art["source"]:
        cut["source"] = art["source"]
        cut["animation"] = art.get("transform", {}).get("animation", "zoom-in")
    else:
        cut["source"] = ""
        cut["type"] = ctype
        cut.update(props)
    comp_cuts.append(cut)
composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": comp_cuts, "overlays": [], "captions": captions,
    "audio": {
        "narration": {"src": PUB("teaser_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("teaser_music.mp3"), "volume": 0.16, "fadeInSeconds": 0.5, "fadeOutSeconds": 1.5},
    },
    "themeConfig": THEME, "metadata": artifact["metadata"],
}
json.dump(composition, open(P / "artifacts/composition.json", "w"), indent=2)

from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
manifest = {"version": "1.0", "assets": [
    {"id": c["id"] + "-img", "type": "image", "path": c["source"], "source_tool": "staged", "scene_id": c["id"]}
    for c in comp_cuts if c.get("source")]}
proposal = json.load(open(P / "artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition, "asset_manifest": manifest,
    "proposal_packet": proposal,
    "script_text": "This is a real question on a real membership site. And this answer? Built from the site's actual numbers and a library of expert playbooks in about four seconds. It knows your site. It learns your business. It gets smarter every day. MembersIntel. Coming soon to MemberPress.",
    "profile": "youtube_shorts", "output_path": str(P / "renders/teaser-vertical.mp4"),
    "remotion_timeout_ms": 600000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
