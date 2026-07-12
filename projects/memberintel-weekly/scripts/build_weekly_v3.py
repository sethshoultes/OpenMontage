"""Weekly recap v3: ONE continuous ElevenLabs v3 TTS call with audio tags,
scene timing derived from whisper word-alignment anchors (no stitched seams).

Usage: build_weekly_v3.py <week_v3.json>

week_v3.json adds:
  "narration_v3": single tagged string (v3 audio tags in [brackets])
  "anchors": {"kpis": "<phrase>", "highlights": "<phrase>", "next": "<phrase>"}
Falls back to eleven_multilingual_v2 (tags stripped) if the v3 call fails.
"""
import json
import re
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
OUTNAME = data["output"] + "-v3"
TAGGED = data["narration_v3"]
PLAIN = re.sub(r"\[[^\]]+\]\s*", "", TAGGED)

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

from tools.tool_registry import registry
registry.discover()
tts = registry.get("tts_selector")
raw = P / f"assets/narration/{OUTNAME}-raw.mp3"

r = tts.execute({"text": TAGGED, "preferred_provider": "elevenlabs",
    "voice_id": "J8hhQxHTArNAtWDmol2o", "model_id": "eleven_v3",
    "stability": 0.5, "similarity_boost": 0.85,
    "output_path": str(raw)})
if not r.success:
    print(f"v3 call failed ({r.error}); falling back to multilingual_v2 single call")
    r = tts.execute({"text": PLAIN, "preferred_provider": "elevenlabs",
        "voice_id": "J8hhQxHTArNAtWDmol2o", "model_id": "eleven_multilingual_v2",
        "stability": 0.50, "similarity_boost": 0.85, "style": 0.30, "speed": 1.0,
        "output_path": str(raw)})
    assert r.success, r.error
NARR_DUR = dur(raw)
print(f"single-call narration: {NARR_DUR:.1f}s")

LEAD, TAIL = 1.2, 3.0
TOTAL = round(LEAD + NARR_DUR + TAIL, 2)
narr_full = P / f"assets/narration/{OUTNAME}-full.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
                "-filter_complex", f"adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad=whole_dur={TOTAL}",
                "-c:a", "libmp3lame", "-q:a", "2", str(narr_full)], check=True)
subprocess.run(["cp", str(narr_full), str(PUBDIR / f"{OUTNAME}_narration.mp3")], check=True)

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(narr_full), word_timestamps=True, language="en")
words = []
captions = []
for seg in segments:
    for w in seg.words or []:
        words.append((w.word.strip().lower(), w.start))
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})
print(len(captions), "caption words")

def anchor_time(phrase, default):
    """Time of the first word of the first fuzzy occurrence of phrase."""
    target = [t.strip(".,!?").lower() for t in phrase.split()]
    seq = [w for w, _ in words]
    for i in range(len(seq) - len(target) + 1):
        if all(target[j] in seq[i + j] for j in range(len(target))):
            return round(words[i][1] - 0.15, 2)
    print(f"WARN anchor not found: {phrase!r}, using default {default}")
    return default

t_kpis = anchor_time(data["anchors"]["kpis"], TOTAL * 0.10)
t_high = anchor_time(data["anchors"]["highlights"], TOTAL * 0.55)
t_next = anchor_time(data["anchors"]["next"], TOTAL * 0.75)
print(f"anchors: kpis@{t_kpis} highlights@{t_high} next@{t_next} / total {TOTAL}")
assert 0 < t_kpis < t_high < t_next < TOTAL - 4, "anchor ordering failed"

CUTS = [
    {"id": "c1", "source": "", "type": "hero_title", "text": f"MembersIntel — {data['week_label']}",
     "heroSubtitle": "the week in review", "backgroundColor": BG,
     "in_seconds": 0.0, "out_seconds": t_kpis, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c2", "source": "", "type": "kpi_grid", "title": "The week in numbers",
     "chartData": [{"label": k["label"], "value": k["value"]} for k in data["kpis"]],
     "columns": min(4, len(data["kpis"])), "chartAnimation": "count-up", "backgroundColor": BG,
     "in_seconds": t_kpis, "out_seconds": t_high, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c3", "source": "", "type": "callout", "callout_type": "info", "title": "Highlights",
     "text": "\n".join("• " + h for h in data["highlights"]), "backgroundColor": BG,
     "in_seconds": t_high, "out_seconds": t_next, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4", "source": "", "type": "callout", "callout_type": "tip", "title": "Next week",
     "text": "\n".join("• " + n for n in data["next_week"]), "backgroundColor": BG,
     "in_seconds": t_next, "out_seconds": round(TOTAL - 2.5, 2), "transition_in": "fade", "transition_out": "fade"},
    {"id": "c5", "source": "", "type": "text_card", "text": "Details in the thread.",
     "color": NAVY, "backgroundColor": BG, "fontSize": 56,
     "in_seconds": round(TOTAL - 2.5, 2), "out_seconds": TOTAL, "transition_in": "fade", "transition_out": "fade"},
]

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
                 "notes": "v3 single-call narration with audio tags; scene timing via whisper anchors."},
}
json.dump(composition, open(P / f"artifacts/{OUTNAME}-composition.json", "w"), indent=2)

vc = registry.get("video_compose")
proposal = json.load(open(ROOT / "projects/memberintel-brains/artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition,
    "asset_manifest": {"version": "1.0", "assets": []},
    "proposal_packet": proposal, "script_text": PLAIN,
    "profile": "youtube_landscape", "output_path": str(P / f"renders/{OUTNAME}.mp4"),
    "remotion_timeout_ms": 600000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED", f"({TOTAL}s)")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
