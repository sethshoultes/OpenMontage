"""Case-study TEMPLATE video (~55s) with clearly-labeled SAMPLE data.

When real beta results exist: edit CASE below (numbers + narration), rerun.
Native comparison/kpi scenes make the data swap a 5-minute job.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-casestudy"
PUBDIR = ROOT / "remotion-composer/public/mi-brains"
BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"; ORANGE = "#F97316"
PUB = lambda n: f"mi-brains/{n}"

CASE = {
    "before_label": "FAILED RENEWALS / MO", "before": "41",
    "after_label": "ONE MONTH LATER", "after": "24",
    "delta": "-41%",
    "kpis": [{"label": "recovered members", "value": 17}, {"label": "playbook applied", "value": 1}, {"label": "setup time (min)", "value": 10}],
}

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

SECTIONS = ["cs1", "cs2", "cs3"]
D = {s: dur(P / f"assets/narration/{s}.mp3") for s in SECTIONS}
LEAD, GAP, TAIL = 1.2, 0.7, 3.5
NARR = {}
t = LEAD
for s in SECTIONS:
    NARR[s] = round(t, 2); t += D[s] + GAP
TOTAL = round(t - GAP + TAIL, 2)

w2 = (NARR["cs2"], NARR["cs3"])
mid2 = round(w2[0] + (w2[1] - w2[0]) * 0.55, 2)
CUTS = [
    {"id": "c1", "source": PUB("cs-title.png"), "animation": "zoom-in",
     "in_seconds": 0.0, "out_seconds": NARR["cs2"], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c2", "source": "", "type": "comparison", "title": "SAMPLE — failed renewals per month",
     "leftLabel": CASE["before_label"], "leftValue": CASE["before"],
     "rightLabel": CASE["after_label"], "rightValue": CASE["after"],
     "backgroundColor": BG, "cardBackgroundColor": "#FFFFFF", "textColor": NAVY,
     "leftColor": ORANGE, "rightColor": TEAL,
     "in_seconds": w2[0], "out_seconds": mid2, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c3", "source": "", "type": "kpi_grid", "title": "SAMPLE — one month in",
     "chartData": [{"label": k["label"], "value": k["value"]} for k in CASE["kpis"]],
     "columns": 3, "chartAnimation": "count-up", "backgroundColor": BG,
     "in_seconds": mid2, "out_seconds": w2[1], "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4", "source": "", "type": "callout", "callout_type": "info", "title": "The case-study pattern",
     "text": "• A real question\n• A grounded answer\n• A playbook applied\n• A number that moved",
     "backgroundColor": BG,
     "in_seconds": NARR["cs3"], "out_seconds": round(TOTAL - 2.5, 2), "transition_in": "fade", "transition_out": "fade"},
    {"id": "c5", "source": "", "type": "text_card", "text": "Template ready for real beta results.",
     "color": NAVY, "backgroundColor": BG, "fontSize": 54,
     "in_seconds": round(TOTAL - 2.5, 2), "out_seconds": TOTAL, "transition_in": "fade", "transition_out": "fade"},
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
subprocess.run(["cp", str(P / "assets/narration/narration_full.mp3"), str(PUBDIR / "cs_narration.mp3")], check=True)
subprocess.run(["cp", str(P / "assets/music/background_music.mp3"), str(PUBDIR / "cs_music.mp3")], check=True)

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
        {"type": "stat_reveal", "in_seconds": round(w2[0] + 1.5, 2), "out_seconds": round(mid2 - 0.5, 2),
         "text": CASE["delta"], "subtitle": "SAMPLE data", "accentColor": TEAL, "position": "bottom-right"},
    ], "captions": captions,
    "audio": {
        "narration": {"src": PUB("cs_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("cs_music.mp3"), "volume": 0.11, "fadeInSeconds": 0.8, "fadeOutSeconds": 2.5},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": ORANGE, "backgroundColor": BG,
        "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, ORANGE, NAVY],
        "springConfig": {"damping": 22, "stiffness": 150, "mass": 1},
        "transitionDuration": 0.35,
        "captionHighlightColor": TEAL, "captionTextColor": NAVY,
        "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
    },
    "metadata": {"project_id": "memberintel-casestudy", "target_duration_seconds": TOTAL,
                 "notes": "Case-study TEMPLATE with SAMPLE-labeled data; swap CASE dict + narration when real beta results land."},
}
json.dump(composition, open(P / "artifacts/composition.json", "w"), indent=2)

from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
manifest = {"version": "1.0", "assets": [
    {"id": "c1-img", "type": "image", "path": PUB("cs-title.png"), "source_tool": "staged", "scene_id": "c1"}]}
proposal = json.load(open(ROOT / "projects/memberintel-brains/artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition, "asset_manifest": manifest,
    "proposal_packet": proposal,
    "script_text": "This is a template with illustrative sample numbers. Before: forty-one failed renewals. After: twenty-four. The case study pattern: a real question, a grounded answer, a playbook applied, a number that moved.",
    "profile": "youtube_landscape", "output_path": str(P / "renders/casestudy-template.mp4"),
    "remotion_timeout_ms": 600000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED", f"({TOTAL}s)")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
