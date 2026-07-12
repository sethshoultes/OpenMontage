"""Build + render 'A Note from Seth' launch announcement (~45s). Seth's cloned ElevenLabs voice, no HeyGen."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-announcement"
PUBDIR = ROOT / "remotion-composer/public/mi-brains"
BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"
PUB = lambda n: f"mi-brains/{n}"

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

SECTIONS = ["a1", "a2", "a3", "a4"]
D = {s: dur(P / f"assets/narration/{s}.mp3") for s in SECTIONS}
LEAD, GAP, TAIL = 1.2, 0.6, 3.5
NARR = {}
t = LEAD
for s in SECTIONS:
    NARR[s] = round(t, 2); t += D[s] + GAP
TOTAL = round(t - GAP + TAIL, 2)

def win(s):
    i = SECTIONS.index(s)
    return (0.0 if i == 0 else NARR[s], TOTAL if i == len(SECTIONS) - 1 else NARR[SECTIONS[i + 1]])

w4 = win("a4")
mid4 = round(w4[0] + (w4[1] - w4[0]) * 0.62, 2)
CUTS = [
    {"id": "c1", "source": PUB("ann-title.png"), "animation": "zoom-in",
     "in_seconds": win("a1")[0], "out_seconds": win("a1")[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c2", "source": PUB("ann-live.png"), "animation": "zoom-in",
     "in_seconds": win("a2")[0], "out_seconds": win("a2")[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c3", "source": PUB("ann-ask.png"), "animation": "zoom-in",
     "in_seconds": win("a3")[0], "out_seconds": win("a3")[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4a", "source": PUB("ann-bar.png"), "animation": "zoom-in",
     "in_seconds": w4[0], "out_seconds": mid4, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4b", "source": PUB("logo-card.png"), "animation": "static",
     "in_seconds": mid4, "out_seconds": TOTAL, "transition_in": "fade", "transition_out": "fade"},
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
subprocess.run(["cp", str(P / "assets/narration/narration_full.mp3"), str(PUBDIR / "ann_narration.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/music/background_music.mp3"), str(PUBDIR / "ann_music.mp3")], check=True)

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(P / "assets/narration/narration_full.mp3"), word_timestamps=True, language="en")
captions = []
for seg in segments:
    for w in seg.words or []:
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [], "captions": captions,
    "audio": {
        "narration": {"src": PUB("ann_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("ann_music.mp3"), "volume": 0.09, "fadeInSeconds": 0.8, "fadeOutSeconds": 2.5},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": "#F97316", "backgroundColor": BG,
        "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, NAVY, "#F97316"],
        "springConfig": {"damping": 24, "stiffness": 140, "mass": 1},
        "transitionDuration": 0.4,
        "captionHighlightColor": TEAL, "captionTextColor": NAVY,
        "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
    },
    "metadata": {"project_id": "memberintel-announcement", "target_duration_seconds": TOTAL,
                 "notes": "A Note from Seth — cloned ElevenLabs Seth voice + portrait from his avatar library; HeyGen-free redirection per user."},
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
    "script_text": "Hey team Seth here. MembersIntel goes live this month, internal beta on memberpress.com. Use it, push on it, thumbs-down anything weak. Black Friday case studies come from this beta. Go ask it something hard.",
    "profile": "youtube_landscape", "output_path": str(P / "renders/announcement.mp4"),
    "remotion_timeout_ms": 600000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED", f"({TOTAL}s)")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
