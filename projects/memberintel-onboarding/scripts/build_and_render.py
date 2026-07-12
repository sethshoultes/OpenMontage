"""Build + render 'Getting Started with MembersIntel' (~85s). Reuses Maya mockups + sync/brand cards."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-onboarding"
PUBDIR = ROOT / "remotion-composer/public/mi-brains"
BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"
PUB = lambda n: f"mi-brains/{n}"

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

SECTIONS = ["o1", "o2", "o3", "o4", "o5"]
D = {s: dur(P / f"assets/narration/{s}.mp3") for s in SECTIONS}
LEAD, GAP, TAIL = 1.5, 0.8, 4.0
NARR = {}
t = LEAD
for s in SECTIONS:
    NARR[s] = round(t, 2); t += D[s] + GAP
TOTAL = round(t - GAP + TAIL, 2)

def win(s):
    i = SECTIONS.index(s)
    return (0.0 if i == 0 else NARR[s], TOTAL if i == len(SECTIONS) - 1 else NARR[SECTIONS[i + 1]])

w4 = win("o4")
mid4 = round(w4[0] + (w4[1] - w4[0]) * 0.45, 2)
w5 = win("o5")
mid5 = round(w5[0] + (w5[1] - w5[0]) * 0.55, 2)
CUTS = [
    {"id": "c1", "source": "", "type": "hero_title", "text": "Getting started with MembersIntel",
     "heroSubtitle": "about ten minutes, start to first answer", "backgroundColor": BG,
     "in_seconds": win("o1")[0], "out_seconds": win("o1")[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c2", "source": PUB("onb-connect.png"), "animation": "zoom-in",
     "in_seconds": win("o2")[0], "out_seconds": win("o2")[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c3", "source": PUB("sync-pull.png"), "animation": "zoom-in",
     "in_seconds": win("o3")[0], "out_seconds": win("o3")[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4a", "source": PUB("maya-q.png"), "animation": "zoom-in",
     "in_seconds": w4[0], "out_seconds": mid4, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4b", "source": PUB("maya-a.png"), "animation": "zoom-in",
     "in_seconds": mid4, "out_seconds": w4[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c5a", "source": PUB("shaped-by-chat.png"), "animation": "zoom-in",
     "in_seconds": w5[0], "out_seconds": mid5, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c5b", "source": PUB("logo-card.png"), "animation": "static",
     "in_seconds": mid5, "out_seconds": TOTAL, "transition_in": "fade", "transition_out": "fade"},
]

inputs, filters = [], []
for i, s in enumerate(SECTIONS):
    inputs += ["-i", str(P / f"assets/narration/{s}.mp3")]
    ms = int(NARR[s] * 1000)
    filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(SECTIONS)))
fc = ";".join(filters) + f";{mix}amix=inputs={len(SECTIONS)}:normalize=0,apad=whole_dur={TOTAL}[out]"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2", str(P / "assets/narration/narration_full.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/narration/narration_full.mp3"), str(PUBDIR / "onb_narration.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/music/background_music.mp3"), str(PUBDIR / "onb_music.mp3")], check=True)

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(P / "assets/narration/narration_full.mp3"), word_timestamps=True, language="en")
captions = []
for seg in segments:
    for w in seg.words or []:
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [
        {"type": "section_title", "in_seconds": round(NARR["o2"] + 0.4, 2), "out_seconds": round(NARR["o2"] + 4.4, 2),
         "text": "1 — CONNECT", "accentColor": TEAL, "position": "top-left"},
        {"type": "section_title", "in_seconds": round(NARR["o3"] + 0.4, 2), "out_seconds": round(NARR["o3"] + 4.4, 2),
         "text": "2 — FIRST SYNC", "accentColor": TEAL, "position": "top-left"},
        {"type": "section_title", "in_seconds": round(NARR["o4"] + 0.4, 2), "out_seconds": round(NARR["o4"] + 4.4, 2),
         "text": "3 — JUST ASK", "accentColor": TEAL, "position": "top-left"},
    ], "captions": captions,
    "audio": {
        "narration": {"src": PUB("onb_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("onb_music.mp3"), "volume": 0.11, "fadeInSeconds": 1.0, "fadeOutSeconds": 3.0},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": "#F97316", "backgroundColor": BG,
        "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, NAVY, "#F97316"],
        "springConfig": {"damping": 24, "stiffness": 135, "mass": 1},
        "transitionDuration": 0.4,
        "captionHighlightColor": TEAL, "captionTextColor": NAVY,
        "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
    },
    "metadata": {"project_id": "memberintel-onboarding", "target_duration_seconds": TOTAL,
                 "notes": "Getting-started walkthrough; synthetic/mockup UI only so it stays current as the real UI evolves."},
}
json.dump(composition, open(P / "artifacts/composition.json", "w"), indent=2)

from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
manifest = {"version": "1.0", "assets": [
    {"id": c["id"] + "-img", "type": "image", "path": c["source"], "source_tool": "staged", "scene_id": c["id"]}
    for c in CUTS if c.get("source")]}
proposal = json.load(open(ROOT / "projects/memberintel-maya/artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition, "asset_manifest": manifest,
    "proposal_packet": proposal,
    "script_text": "Getting started with MembersIntel takes about ten minutes. Connect the plugin. Your first sync runs. Then just ask real questions in plain language. Shape it as you go and it gets smarter every week.",
    "profile": "youtube_landscape", "output_path": str(P / "renders/onboarding.mp4"),
    "remotion_timeout_ms": 900000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED", f"({TOTAL}s)")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
