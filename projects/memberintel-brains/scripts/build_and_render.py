"""Build + render 'One Question' v2 (post Q2-review recut).

Timeline computed dynamically from actual narration durations.
Act 2a is conceptual (knows-cards / shaped-by-chat / PRIVATE); Act 1 uses the
masked capture (citation chip + SOURCES row removed); scene-15 is the note-card.
"""
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-brains"

BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"; ORANGE = "#F97316"
PUB = lambda n: f"mi-brains/{n}"

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

SECTIONS = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10"]
D = {s: dur(P / f"assets/narration/{s}.mp3") for s in SECTIONS}

LEAD = 3.0; GAP = 0.9; TAIL = 6.5
NARR = {}
t = LEAD
for s in SECTIONS:
    NARR[s] = round(t, 2)
    t += D[s] + GAP
TOTAL = round(t - GAP + TAIL, 2)
END = {s: round(NARR[s] + D[s], 2) for s in SECTIONS}

# Scene boundaries: each section's visual window runs from its narration start
# (minus a small pre-roll) to the next section's start. Splits are fractions.
def win(s):
    i = SECTIONS.index(s)
    start = 0.0 if i == 0 else NARR[s]
    end = TOTAL if i == len(SECTIONS) - 1 else NARR[SECTIONS[i + 1]]
    return start, end

def split(s, *fracs):
    a, b = win(s)
    pts = [a] + [round(a + (b - a) * f, 2) for f in fracs] + [b]
    return list(zip(pts, pts[1:]))

w1 = win("s1"); w2 = win("s2"); w3 = win("s3")
s4a, s4b = split("s4", 0.45)
s5a, s5b, s5c = split("s5", 0.42, 0.74)
s6a, s6b = split("s6", 0.62)
w7 = win("s7")
s8a, s8b = split("s8", 0.55)
s9a, s9b = split("s9", 0.62)
w10 = win("s10")

CUTS = [
    ("cut-1", None, *w1, {}, {"source": PUB("app-chat-answer-masked.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-1 real churn Q&A (masked per Q2: no citation UI)"}),
    ("cut-2", "screenshot_scene", *w2,
     {"backgroundImage": PUB("app-chat-answer-masked.png"), "screenshotSize": {"width": 1920, "height": 1080},
      "accentColor": TEAL, "backgroundColor": BG,
      "screenshotSteps": [
        {"kind": "pause", "seconds": 1.2},
        {"kind": "highlight_box", "region": {"x": 0.385, "y": 0.165, "width": 0.375, "height": 0.115}, "durationSeconds": 5.0, "color": TEAL},
        {"kind": "pause", "seconds": 4.0},
        {"kind": "highlight_box", "region": {"x": 0.390, "y": 0.508, "width": 0.038, "height": 0.045}, "durationSeconds": 4.5, "color": TEAL},
      ]},
     {"source": "", "reason": "scene-2 anatomy: numbers + thumbs only (citation/sources highlights removed per Q2)"}),
    ("cut-3", "anime_scene", *w3, {"images": [PUB("split-a.png"), PUB("split-b.png")], "animation": "static", "vignette": False},
     {"source": "", "reason": "scene-3 two-brains split"}),
    ("cut-4", None, *s4a, {}, {"source": PUB("knows-a.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-4 knows: who you are + your site"}),
    ("cut-5", None, *s4b, {}, {"source": PUB("knows-b.png"), "transform": {"animation": "static"}, "reason": "scene-5 knows: all four layers"}),
    ("cut-6", None, *s5a, {}, {"source": PUB("knows-b.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-6 knows hold through right-now/learned beats"}),
    ("cut-7", None, *s5b, {}, {"source": PUB("shaped-by-chat.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-7 shaped by conversation (Blair framing)"}),
    ("cut-8", None, *s5c, {}, {"source": PUB("privacy-b.png"), "transform": {"animation": "static"}, "reason": "scene-8 PRIVATE full stop"}),
    ("cut-9", None, *s6a, {}, {"source": PUB("shelves.png"), "transform": {"animation": "ken-burns"}, "reason": "scene-9 library shelves"}),
    ("cut-10", None, *s6b, {}, {"source": PUB("admin-global-brain.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-10 real admin corpus (masked)"}),
    ("cut-11", "anime_scene", *w7, {"images": [PUB("gate-a.png"), PUB("gate-b.png")], "animation": "static", "vignette": False},
     {"source": "", "reason": "scene-11 approval gate"}),
    ("cut-12", None, *s8a, {}, {"source": PUB("flywheel-today.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-12 flywheel TODAY"}),
    ("cut-13", None, *s8b, {}, {"source": PUB("flywheel-next.png"), "transform": {"animation": "static"}, "reason": "scene-13 flywheel NEXT"}),
    ("cut-14", None, *s9a, {}, {"source": PUB("flywheel-future.png"), "transform": {"animation": "zoom-out"}, "reason": "scene-14 flywheel FUTURE (hero)"}),
    ("cut-15", None, *s9b, {}, {"source": PUB("note-card.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-15 note-to-self payoff (hero, conceptual per Q2)"}),
    ("cut-16", "text_card", *w10, {"text": "Two brains. One private, one shared.", "color": NAVY, "backgroundColor": BG, "fontSize": 72},
     {"source": "", "reason": "scene-16 closing card"}),
]

OVERLAYS = [
    {"type": "section_title", "in_seconds": round(w1[1] - 3.5, 2), "out_seconds": round(w1[1] - 0.1, 2), "text": "ONE QUESTION", "accentColor": TEAL, "position": "bottom-center"},
    {"type": "section_title", "in_seconds": round(NARR["s4"] + 1.0, 2), "out_seconds": round(NARR["s4"] + 5.5, 2), "text": "THE MEMBER BRAIN", "accentColor": TEAL, "position": "top-left"},
    {"type": "section_title", "in_seconds": round(NARR["s6"] + 1.5, 2), "out_seconds": round(NARR["s6"] + 6.0, 2), "text": "THE SHARED LIBRARY", "accentColor": NAVY, "position": "top-left"},
    {"type": "stat_reveal", "in_seconds": round(s6b[0] + 2.0, 2), "out_seconds": round(s6b[1] - 1.0, 2), "text": "98 playbooks", "subtitle": "written & reviewed by the team", "accentColor": TEAL, "position": "bottom-right"},
]

THEME = {
    "primaryColor": TEAL, "accentColor": ORANGE, "backgroundColor": BG,
    "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
    "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
    "chartColors": [TEAL, NAVY, ORANGE, "#7DD3E8", "#94A3B8"],
    "springConfig": {"damping": 26, "stiffness": 120, "mass": 1},
    "transitionDuration": 0.45,
    "captionHighlightColor": TEAL,
    "captionTextColor": NAVY,
    "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
}

# ---------- narration_full ----------
inputs = []
filters = []
for i, s in enumerate(SECTIONS):
    inputs += ["-i", str(P / f"assets/narration/{s}.mp3")]
    ms = int(NARR[s] * 1000)
    filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(SECTIONS)))
fc = ";".join(filters) + f";{mix}amix=inputs={len(SECTIONS)}:normalize=0,apad=whole_dur={TOTAL}[out]"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2", str(P / "assets/narration/narration_full.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/narration/narration_full.mp3"),
                str(ROOT / "remotion-composer/public/mi-brains/narration_full.mp3")], check=True)
print(f"narration_full assembled: {TOTAL}s | starts: " + ", ".join(f"{s}@{NARR[s]}" for s in SECTIONS))

# ---------- captions ----------
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(P / "assets/narration/narration_full.mp3"), word_timestamps=True, language="en")
captions = []
for seg in segments:
    for w in seg.words or []:
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})
json.dump(captions, open(P / "artifacts/captions.json", "w"), indent=1)
print(len(captions), "caption words")

# ---------- artifact ----------
artifact_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "source": art["source"], "in_seconds": tin, "out_seconds": tout,
           "layer": "primary", "transition_in": "fade", "transition_out": "fade",
           "transition_duration": 0.45, "reason": art["reason"]}
    if "transform" in art:
        cut["transform"] = art["transform"]
    artifact_cuts.append(cut)
artifact = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": artifact_cuts,
    "audio": {
        "narration": {"segments": [{"asset_id": f"narration-{s}", "start_seconds": NARR[s]} for s in SECTIONS]},
        "music": {"asset_id": "music-bg", "volume": 0.10, "fade_in_seconds": 2.0, "fade_out_seconds": 4.0,
                  "ducking": {"enabled": True, "reduction_db": -8}},
    },
    "subtitles": {"enabled": True, "style": "word-by-word", "source": "artifacts/captions.json",
                  "font": "Inter", "position": "bottom-center"},
    "metadata": {"project_id": "memberintel-brains", "playbook": "custom-membersintel-brand",
                 "target_duration_seconds": TOTAL,
                 "notes": "v2 recut per Q2 review (decision d5): conceptual Act 2a, masked capture, note-card payoff. Timeline computed from actual narration durations."},
}
jsonschema.validate(artifact, json.load(open(ROOT / "schemas/artifacts/edit_decisions.schema.json")))
json.dump(artifact, open(P / "artifacts/edit_decisions.json", "w"), indent=2)
print("edit_decisions artifact: VALID")

# ---------- composition + render ----------
comp_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "in_seconds": tin, "out_seconds": tout, "transition_in": "fade", "transition_out": "fade"}
    if art["source"]:
        cut["source"] = art["source"]
        cut["animation"] = art.get("transform", {}).get("animation", "ken-burns")
    else:
        cut["source"] = ""
        cut["type"] = ctype
        cut.update(props)
    comp_cuts.append(cut)
composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": comp_cuts, "overlays": OVERLAYS, "captions": captions,
    "audio": {
        "narration": {"src": PUB("narration_full.mp3"), "volume": 1.0},
        "music": {"src": PUB("background_music.mp3"), "volume": 0.10, "fadeInSeconds": 2.0, "fadeOutSeconds": 4.0},
    },
    "themeConfig": THEME, "metadata": artifact["metadata"],
}
json.dump(composition, open(P / "artifacts/composition.json", "w"), indent=2)
print(f"composition: {len(comp_cuts)} cuts, {len(OVERLAYS)} overlays")

from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
manifest = {"version": "1.0", "assets": [
    {"id": c["id"] + "-img", "type": "image", "path": c["source"], "source_tool": "staged", "scene_id": c["id"]}
    for c in comp_cuts if c.get("source")]}
proposal = json.load(open(P / "artifacts/proposal_packet.json"))
script = json.load(open(P / "artifacts/script.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition, "asset_manifest": manifest,
    "proposal_packet": proposal, "script_text": " ".join(s["text"] for s in script["sections"]),
    "profile": "youtube_landscape", "output_path": str(P / "renders/final-v2.mp4"),
    "remotion_timeout_ms": 1500000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
