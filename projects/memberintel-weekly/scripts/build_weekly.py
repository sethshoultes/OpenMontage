"""Parameterized weekly status recap builder.

Usage: python build_weekly.py <week_data.json>

week_data.json:
{
  "week_label": "Week of July 7",
  "prs_merged": 10, "commits": 126,
  "narration": {"w1": "...", "w2": "...", "w3": "...", "w4": "..."},
  "kpis": [{"label": "PRs merged", "value": 10}, {"label": "commits", "value": 126}],
  "highlights": ["...", "...", "..."],
  "next_week": ["...", "..."],
  "output": "week-2026-07-07"
}

All scenes are Remotion-native (no image generation). Music bed is reused across
weeks (assets/music/weekly_bed.mp3, generated once). Narration is regenerated
per week. Typical wall time: ~15-20 min, cost ~= $0.15/week (TTS only).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-weekly"
PUBDIR = ROOT / "remotion-composer/public/mi-brains"

BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"; ORANGE = "#F97316"
PUB = lambda n: f"mi-brains/{n}"

data = json.load(open(sys.argv[1]))
OUTNAME = data["output"]

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

# 1. TTS per section
from tools.tool_registry import registry
registry.discover()
tts = registry.get("tts_selector")
SECTIONS = ["w1", "w2", "w3", "w4"]
(P / "assets/narration").mkdir(parents=True, exist_ok=True)
for sid in SECTIONS:
    r = tts.execute({"text": data["narration"][sid], "preferred_provider": "elevenlabs",
        "voice_id": "J8hhQxHTArNAtWDmol2o",  # Seth's cloned voice
        "model_id": "eleven_multilingual_v2",
        "stability": 0.50, "similarity_boost": 0.85, "style": 0.30, "speed": 1.0,
        "output_path": str(P / f"assets/narration/{OUTNAME}-{sid}.mp3")})
    assert r.success, r.error
print("narration ok")

D = {s: dur(P / f"assets/narration/{OUTNAME}-{s}.mp3") for s in SECTIONS}
LEAD, GAP, TAIL = 1.2, 0.7, 3.0
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

w1 = win("w1"); w2 = win("w2"); w3 = win("w3"); w4 = win("w4")
CUTS = [
    {"id": "c1", "source": "", "type": "hero_title", "text": f"MembersIntel — {data['week_label']}",
     "heroSubtitle": "weekly status, 60 seconds", "backgroundColor": BG,
     "in_seconds": w1[0], "out_seconds": w1[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c2", "source": "", "type": "kpi_grid", "title": "The week in numbers",
     "chartData": [{"label": k["label"], "value": k["value"]} for k in data["kpis"]],
     "columns": min(4, len(data["kpis"])), "chartAnimation": "count-up", "backgroundColor": BG,
     "in_seconds": w2[0], "out_seconds": w2[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c3", "source": "", "type": "callout", "callout_type": "info", "title": "Highlights",
     "text": "\n".join("• " + h for h in data["highlights"]), "backgroundColor": BG,
     "in_seconds": w3[0], "out_seconds": w3[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4", "source": "", "type": "callout", "callout_type": "tip", "title": "Next week",
     "text": "\n".join("• " + n for n in data["next_week"]), "backgroundColor": BG,
     "in_seconds": w4[0], "out_seconds": round(TOTAL - 2.5, 2), "transition_in": "fade", "transition_out": "fade"},
    {"id": "c5", "source": "", "type": "text_card", "text": "Details in the thread.",
     "color": NAVY, "backgroundColor": BG, "fontSize": 56,
     "in_seconds": round(TOTAL - 2.5, 2), "out_seconds": TOTAL, "transition_in": "fade", "transition_out": "fade"},
]

# narration assembly + captions
inputs, filters = [], []
for i, s in enumerate(SECTIONS):
    inputs += ["-i", str(P / f"assets/narration/{OUTNAME}-{s}.mp3")]
    ms = int(NARR[s] * 1000)
    filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(SECTIONS)))
fc = ";".join(filters) + f";{mix}amix=inputs={len(SECTIONS)}:normalize=0,apad=whole_dur={TOTAL}[out]"
narr = P / f"assets/narration/{OUTNAME}-full.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2", str(narr)], check=True)
subprocess.run(["cp", str(narr), str(PUBDIR / f"{OUTNAME}_narration.mp3")], check=True)

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(narr), word_timestamps=True, language="en")
captions = []
for seg in segments:
    for w in seg.words or []:
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [], "captions": captions,
    "audio": {
        "narration": {"src": PUB(f"{OUTNAME}_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("weekly_bed.mp3"), "volume": 0.10, "fadeInSeconds": 0.5, "fadeOutSeconds": 2.0},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": ORANGE, "backgroundColor": BG,
        "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, NAVY, ORANGE],
        "springConfig": {"damping": 22, "stiffness": 150, "mass": 1},
        "transitionDuration": 0.35,
        "captionHighlightColor": TEAL, "captionTextColor": NAVY,
        "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
    },
    "metadata": {"project_id": "memberintel-weekly", "video": OUTNAME, "target_duration_seconds": TOTAL,
                 "notes": "Weekly recap from template; data-driven, Remotion-native scenes only."},
}
(P / "artifacts").mkdir(exist_ok=True)
json.dump(composition, open(P / f"artifacts/{OUTNAME}-composition.json", "w"), indent=2)

vc = registry.get("video_compose")
proposal = json.load(open(ROOT / "projects/memberintel-brains/artifacts/proposal_packet.json"))
(P / "renders").mkdir(exist_ok=True)
r = vc.execute({
    "operation": "render", "edit_decisions": composition,
    "asset_manifest": {"version": "1.0", "assets": []},
    "proposal_packet": proposal,
    "script_text": " ".join(data["narration"][s] for s in SECTIONS),
    "profile": "youtube_landscape", "output_path": str(P / f"renders/{OUTNAME}.mp4"),
    "remotion_timeout_ms": 600000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED", f"({TOTAL}s)")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
