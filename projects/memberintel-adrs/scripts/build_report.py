"""Render a report explainer video from report.json.

Usage: build_report.py <report.json> [profile]
Env:   ELEVENLABS_API_KEY (TTS + music), SETH_VOICE_ID (default: Seth's clone)

Scene grammar: hero title -> "The big picture" KPI grid -> one comparison
card per finding -> "Worth knowing" callout -> takeaway card. Same
single-take v3 narration + whisper-anchored cuts as the ADR template.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
P = ROOT / "projects" / "memberintel-adrs"
PUBDIR = ROOT / "remotion-composer/public/mi-adrs"
PUBDIR.mkdir(parents=True, exist_ok=True)
PUB = lambda n: f"mi-adrs/{n}"
(P / "assets/narration").mkdir(parents=True, exist_ok=True)
(P / "artifacts").mkdir(exist_ok=True)
(P / "renders").mkdir(exist_ok=True)

BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"; ORANGE = "#F97316"
REP = json.load(open(sys.argv[1]))
PROFILE = sys.argv[2] if len(sys.argv) > 2 else "youtube_landscape"
OUTNAME = REP["output"]
VOICE = os.environ.get("SETH_VOICE_ID", "J8hhQxHTArNAtWDmol2o")

TAGGED = REP["narration"]
PLAIN = re.sub(r"\[[^\]]+\]\s*", "", TAGGED)

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

from tools.tool_registry import registry
registry.discover()
tts = registry.get("tts_selector")
raw = P / f"assets/narration/{OUTNAME}-raw.mp3"
r = tts.execute({"text": TAGGED, "preferred_provider": "elevenlabs",
    "voice_id": VOICE, "model_id": "eleven_v3",
    "stability": 0.50, "similarity_boost": 0.85,
    "output_path": str(raw)})
if not r.success:
    print(f"eleven_v3 failed ({r.error}); falling back to multilingual_v2, tags stripped")
    r = tts.execute({"text": PLAIN, "preferred_provider": "elevenlabs",
        "voice_id": VOICE, "model_id": "eleven_multilingual_v2",
        "stability": 0.50, "similarity_boost": 0.85, "style": 0.30, "speed": 1.0,
        "output_path": str(raw)})
    assert r.success, r.error
NARR_DUR = dur(raw)
print(f"single-call narration: {NARR_DUR:.1f}s")

LEAD, TAIL = 1.2, 3.0
TOTAL = round(LEAD + NARR_DUR + TAIL, 2)

bed = PUBDIR / "adr_bed.mp3"
if not bed.exists() or dur(bed) < TOTAL:
    music = registry.get("music_gen")
    r = music.execute({
        "prompt": "Calm focused tech documentary score, soft pulse, curious, understated, loops well, instrumental only",
        "duration_seconds": int(TOTAL) + 2, "output_path": str(bed)})
    assert r.success, r.error
assert bed.stat().st_size > 10000, "bed missing"

narr = P / f"assets/narration/{OUTNAME}-full.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
                "-filter_complex", f"adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad=whole_dur={TOTAL}",
                "-c:a", "libmp3lame", "-q:a", "2", str(narr)], check=True)
subprocess.run(["cp", str(narr), str(PUBDIR / f"{OUTNAME}_narration.mp3")], check=True)

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(str(narr), word_timestamps=True, language="en")
words = []
captions = []
for seg in segments:
    for w in seg.words or []:
        for part in re.split(r"[-–]", w.word.strip()):
            if part:
                words.append((part, float(w.start)))
        captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})
print(len(captions), "caption words")

NUM_WORDS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
             "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
             "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
             "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
             "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
             "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
             "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000"}

def norm(tok):
    t = tok.strip(".,!?…:;").lower()
    return NUM_WORDS.get(t, t)

def tok_match(t, w):
    return t == w or (len(t) >= 3 and t.isalpha() and w.startswith(t))

def anchor_time(phrase, default, start=0):
    """(time, next_start) of the first occurrence of phrase at/after start."""
    target = [norm(t) for tok in phrase.split() for t in re.split(r"[-–]", tok) if t]
    for i in range(start, len(words) - len(target) + 1):
        if all(tok_match(target[j], norm(words[i + j][0])) for j in range(len(target))):
            return round(max(0.0, words[i][1] - 0.15), 2), i + len(target)
    print(f"WARN anchor not found: {phrase!r}, using default {default}")
    return default, start

t_kpis, idx = anchor_time(REP["anchors"]["kpis"], round(TOTAL * 0.08, 2))
raw_changes = []
for c in REP.get("changes", []):
    t, idx = anchor_time(c["anchor"], None, idx)
    if t is not None:
        raw_changes.append((t, c))
t_high, idx = anchor_time(REP["anchors"]["highlights"], round(TOTAL * 0.72, 2), idx)
t_wrap, idx = anchor_time(REP["anchors"]["wrap"], round(TOTAL * 0.88, 2), idx)
if not (0 < t_kpis < t_high < t_wrap < TOTAL):
    print(f"WARN anchor ordering failed (kpis@{t_kpis} high@{t_high} wrap@{t_wrap}); using proportional cuts")
    t_kpis, t_high, t_wrap = round(TOTAL * 0.08, 2), round(TOTAL * 0.72, 2), round(TOTAL * 0.88, 2)
    raw_changes = []
print(f"anchors: kpis@{t_kpis} highlights@{t_high} wrap@{t_wrap} / total {TOTAL}")

changes = []
floor = t_kpis + 2.5
for t, c in raw_changes:
    if floor <= t <= t_high - 2.5:
        changes.append((t, c))
        floor = t + 2.5
    else:
        print(f"WARN change anchor out of window, skipping scene: {c['title']!r} @ {t}")
print(f"change scenes: {[(t, c['title']) for t, c in changes]}")

CUTS = [
    {"id": "c1", "source": "", "type": "hero_title", "text": REP["title"],
     "heroSubtitle": "what the data says", "backgroundColor": BG,
     "in_seconds": 0.0, "out_seconds": t_kpis, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c2", "source": "", "type": "kpi_grid", "title": "The big picture",
     "chartData": [{"label": k["label"], "value": k["value"]} for k in REP["kpis"]],
     "columns": min(4, len(REP["kpis"])), "chartAnimation": "count-up", "backgroundColor": BG,
     "in_seconds": t_kpis, "out_seconds": changes[0][0] if changes else t_high,
     "transition_in": "fade", "transition_out": "fade"},
]
for n, (t, c) in enumerate(changes):
    out = changes[n + 1][0] if n + 1 < len(changes) else t_high
    CUTS.append({"id": f"chg{n + 1}", "source": "", "type": "comparison", "title": c["title"],
                 "leftLabel": "plateau", "leftValue": c["before"], "leftColor": "#64748B",
                 "rightLabel": "growth", "rightValue": c["after"], "rightColor": TEAL,
                 "backgroundColor": BG,
                 "in_seconds": t, "out_seconds": out, "transition_in": "fade", "transition_out": "fade"})
CUTS += [
    {"id": "c3", "source": "", "type": "callout", "callout_type": "info", "title": "Worth knowing",
     "text": "\n".join("• " + b for b in REP["highlights"]), "backgroundColor": BG,
     "in_seconds": t_high, "out_seconds": t_wrap, "transition_in": "fade", "transition_out": "fade"},
    {"id": "c4", "source": "", "type": "text_card", "text": REP["takeaway"],
     "color": NAVY, "backgroundColor": BG, "fontSize": 52,
     "in_seconds": t_wrap, "out_seconds": TOTAL, "transition_in": "fade", "transition_out": "fade"},
]

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [], "captions": captions,
    "audio": {
        "narration": {"src": PUB(f"{OUTNAME}_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("adr_bed.mp3"), "volume": 0.10, "fadeInSeconds": 0.5, "fadeOutSeconds": 2.0},
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
    "metadata": {"project_id": "memberintel-adrs", "video": OUTNAME,
                 "target_duration_seconds": TOTAL,
                 "notes": "Report explainer; single-take v3 narration, whisper-anchored scenes."},
}
json.dump(composition, open(P / f"artifacts/{OUTNAME}-composition.json", "w"), indent=2)

vc = registry.get("video_compose")
proposal = json.load(open(ROOT / "projects/memberintel-brains/artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition,
    "asset_manifest": {"version": "1.0", "assets": []},
    "proposal_packet": proposal, "script_text": PLAIN,
    "profile": PROFILE, "output_path": str(P / f"renders/{OUTNAME}.mp4"),
    "remotion_timeout_ms": 900000,
})
if not r.success:
    print("RENDER FAILED:", r.error)
    sys.exit(1)
print("RENDER OK", f"{TOTAL}s ->", P / f"renders/{OUTNAME}.mp4")
