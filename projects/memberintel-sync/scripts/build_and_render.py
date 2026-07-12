"""Build + render 'The Life of a Sync' (~100s landscape, living doc). Dynamic timeline."""
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-sync"
PUBDIR = ROOT / "remotion-composer/public/mi-brains"

BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"
PUB = lambda n: f"mi-brains/{n}"

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

SECTIONS = ["y1", "y2", "y3", "y4", "y5", "y6"]
D = {s: dur(P / f"assets/narration/{s}.mp3") for s in SECTIONS}
LEAD, GAP, TAIL = 2.0, 0.9, 5.0
NARR = {}
t = LEAD
for s in SECTIONS:
    NARR[s] = round(t, 2)
    t += D[s] + GAP
TOTAL = round(t - GAP + TAIL, 2)

def win(s):
    i = SECTIONS.index(s)
    return (0.0 if i == 0 else NARR[s],
            TOTAL if i == len(SECTIONS) - 1 else NARR[SECTIONS[i + 1]])

CUTS = []
IMGS = {"y1": "sync-title.png", "y2": "sync-doors.png", "y3": "sync-pull.png",
        "y4": "sync-prose.png", "y5": "app-chat-answer-masked.png", "y6": "sync-end.png"}
ANIM = {"y1": "static", "y2": "zoom-in", "y3": "zoom-in", "y4": "zoom-in", "y5": "zoom-in", "y6": "static"}
for s in SECTIONS:
    a, b = win(s)
    CUTS.append({"id": f"cut-{s}", "source": PUB(IMGS[s]), "animation": ANIM[s],
                 "in_seconds": a, "out_seconds": b, "transition_in": "fade", "transition_out": "fade"})

# narration_full + captions
inputs, filters = [], []
for i, s in enumerate(SECTIONS):
    inputs += ["-i", str(P / f"assets/narration/{s}.mp3")]
    ms = int(NARR[s] * 1000)
    filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(SECTIONS)))
fc = ";".join(filters) + f";{mix}amix=inputs={len(SECTIONS)}:normalize=0,apad=whole_dur={TOTAL}[out]"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2", str(P / "assets/narration/narration_full.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/narration/narration_full.mp3"), str(PUBDIR / "sync_narration.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/music/background_music.mp3"), str(PUBDIR / "sync_music.mp3")], check=True)

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(P / "assets/narration/narration_full.mp3"), word_timestamps=True, language="en")
captions = []
for seg in segments:
    for w in seg.words or []:
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})
json.dump(captions, open(P / "artifacts/captions.json", "w"), indent=1)
print(f"assembled {TOTAL}s, {len(captions)} caption words")

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [
        {"type": "section_title", "in_seconds": round(NARR["y2"] + 0.5, 2), "out_seconds": round(NARR["y2"] + 5.0, 2),
         "text": "STEP 1 — THE PLUGIN", "accentColor": TEAL, "position": "top-left"},
        {"type": "section_title", "in_seconds": round(NARR["y3"] + 0.5, 2), "out_seconds": round(NARR["y3"] + 5.0, 2),
         "text": "STEP 2 — THE PULL", "accentColor": TEAL, "position": "top-left"},
        {"type": "section_title", "in_seconds": round(NARR["y4"] + 0.5, 2), "out_seconds": round(NARR["y4"] + 5.0, 2),
         "text": "STEP 3 — THE REWRITE", "accentColor": TEAL, "position": "top-left"},
    ], "captions": captions,
    "audio": {
        "narration": {"src": PUB("sync_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("sync_music.mp3"), "volume": 0.10, "fadeInSeconds": 1.5, "fadeOutSeconds": 3.5},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": "#F97316", "backgroundColor": BG,
        "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, NAVY, "#F97316"],
        "springConfig": {"damping": 26, "stiffness": 120, "mass": 1},
        "transitionDuration": 0.45,
        "captionHighlightColor": TEAL, "captionTextColor": NAVY,
        "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
    },
    "metadata": {"project_id": "memberintel-sync", "target_duration_seconds": TOTAL,
                 "notes": "Life of a Sync living-doc video; pull-based flow verified against src/memberintel/api/sites/sync.py."},
}
json.dump(composition, open(P / "artifacts/composition.json", "w"), indent=2)

from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
manifest = {"version": "1.0", "assets": [
    {"id": c["id"] + "-img", "type": "image", "path": c["source"], "source_tool": "staged", "scene_id": c["id"]}
    for c in CUTS]}
proposal = json.load(open(ROOT / "projects/memberintel-brains/artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition, "asset_manifest": manifest,
    "proposal_packet": proposal,
    "script_text": "Every few hours something quiet happens between a WordPress site and MembersIntel. The Connect plugin opens locked doors. MembersIntel pulls what changed into that site's private brain. Every sync rewrites Live Stats as prose. Fresh answers, invisible sync.",
    "profile": "youtube_landscape", "output_path": str(P / "renders/sync.mp4"),
    "remotion_timeout_ms": 900000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
