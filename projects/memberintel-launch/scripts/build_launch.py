"""Single-voice, minimalist-animation launch videos (teaser, before/after, etc).

Usage: build_launch.py <episode.json> [profile]

Same pattern as memberintel-hero/scripts/build_hero.py: ONE continuous
Seth-voice eleven_v3 take for the whole video, forced-alignment
(tools/subtitle/caption_align) against the known-correct script text for
both captions and scene-cut boundaries — never blind ASR guesses, never
stitched per-segment audio. No avatar/talking-head visuals: every segment
is a data-driven Explainer scene (hero_title, text_card, callout,
comparison, stat_card).
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import os
os.chdir(ROOT)
P = ROOT / "projects" / "memberintel-launch"
PUBDIR = ROOT / "remotion-composer/public/mi-launch"
PUBDIR.mkdir(parents=True, exist_ok=True)
PUB = lambda n: f"mi-launch/{n}"
(P / "assets/narration").mkdir(parents=True, exist_ok=True)
(P / "artifacts").mkdir(exist_ok=True)
(P / "renders").mkdir(exist_ok=True)

# Reuse the already-approved hero background art (production-live on
# features/compare/about) instead of generating anything new.
HERO_PUBDIR = ROOT / "remotion-composer/public/mi-hero"
for img in sorted(HERO_PUBDIR.glob("*.png")):
    subprocess.run(["cp", str(img), str(PUBDIR / img.name)], check=True)

SETH_VOICE = "J8hhQxHTArNAtWDmol2o"
LEAD, TAIL = 0.6, 2.2


def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def clean(text):
    """Strips eleven_v3 delivery tags (e.g. "[warm] ") — never spoken, never a caption word."""
    return re.sub(r"\[[^\]]+\]\s*", "", text)


EP = json.load(open(sys.argv[1]))
PROFILE = sys.argv[2] if len(sys.argv) > 2 else EP.get("profile", "instagram_reels")
OUTNAME = EP["output"]
SEGMENTS = EP["segments"]

from tools.tool_registry import registry
registry.discover()
tts = registry.get("tts_selector")

full_text = " ".join(s["narration"] for s in SEGMENTS)
key = hashlib.md5(full_text.encode()).hexdigest()[:8]
narr = P / f"assets/narration/{OUTNAME}-{key}.mp3"
if not (narr.exists() and narr.stat().st_size > 1000):
    r = tts.execute({
        "text": full_text, "preferred_provider": "elevenlabs",
        "voice_id": SETH_VOICE, "model_id": "eleven_v3",
        "stability": 0.50, "similarity_boost": 0.85,
        "output_path": str(narr),
    })
    assert r.success, r.error
NARR_DUR = dur(narr)
TOTAL = round(LEAD + NARR_DUR + TAIL, 2)
subprocess.run(["cp", str(narr), str(PUBDIR / f"{OUTNAME}_narration.mp3")], check=True)
print(f"narration: {NARR_DUR:.2f}s, total: {TOTAL:.2f}s")

bed = PUBDIR / "hero_bed.mp3"
if not bed.exists() or dur(bed) < TOTAL:
    music = registry.get("music_gen")
    r = music.execute({
        "prompt": "Minimal calm corporate tech ambient bed, subtle pads, understated rhythm, unobtrusive, loops well, instrumental only",
        "duration_seconds": int(TOTAL) + 2, "output_path": str(bed)})
    assert r.success, r.error

from faster_whisper import WhisperModel
from tools.subtitle.caption_align import align_words_to_reference

model = WhisperModel("base", device="cpu", compute_type="int8")
reference_words = clean(full_text).split()
whisper_segments, _ = model.transcribe(str(narr), word_timestamps=True, language="en")
whisper_words = [(w.word.strip(), w.start, w.end) for seg in whisper_segments for w in (seg.words or [])]
aligned = align_words_to_reference(whisper_words, reference_words)

captions = [
    {"word": word, "startMs": int((LEAD + start) * 1000), "endMs": int((LEAD + end) * 1000)}
    for word, start, end in aligned
]
print(len(captions), "caption words")

seg_word_counts = [len(clean(s["narration"]).split()) for s in SEGMENTS]
assert sum(seg_word_counts) == len(reference_words), "segment word counts must cover the full script exactly"

CUTS = []
idx = 0
for i, (seg, count) in enumerate(zip(SEGMENTS, seg_word_counts)):
    seg_start = aligned[idx][1]
    seg_end = aligned[idx + count - 1][2]
    idx += count
    cut = dict(seg["cut"])
    cut.setdefault("id", f"s{i:02d}")
    cut.setdefault("source", "")
    cut["in_seconds"] = round(LEAD + seg_start, 2)
    cut["out_seconds"] = round(LEAD + seg_end, 2)
    cut.setdefault("transition_in", "fade")
    cut.setdefault("transition_out", "fade")
    CUTS.append(cut)

END = EP["end"]
CUTS.append({
    "id": "end", "source": "", "type": "hero_title", "text": END["text"],
    "heroSubtitle": END.get("subtitle"), "backgroundColor": END.get("backgroundColor", "#0B0F14"),
    "in_seconds": round(LEAD + NARR_DUR, 2), "out_seconds": TOTAL,
    "transition_in": "fade", "transition_out": "fade",
})

INK = "#0B0F14"; PAPER = "#F8FAFC"; TEAL = "#2DD4BF"; ORANGE = "#F97316"
composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [], "captions": captions,
    "audio": {
        "narration": {"src": PUB(f"{OUTNAME}_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("hero_bed.mp3"), "volume": 0.10, "fadeInSeconds": 0.4, "fadeOutSeconds": 1.8},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": ORANGE, "backgroundColor": INK,
        "surfaceColor": "#111827", "textColor": PAPER, "mutedTextColor": "#94A3B8",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, ORANGE, PAPER],
        "springConfig": {"damping": 18, "stiffness": 200, "mass": 0.9},
        "transitionDuration": 0.25,
        "captionHighlightColor": TEAL, "captionTextColor": PAPER,
        "captionBackgroundColor": "rgba(11, 15, 20, 0.82)",
    },
    "metadata": {"project_id": "memberintel-launch", "video": OUTNAME,
                 "target_duration_seconds": TOTAL,
                 "notes": "Pre-launch social video; no avatars; MESSAGING.md-compliant script."},
}
json.dump(composition, open(P / f"artifacts/{OUTNAME}-composition.json", "w"), indent=2)

vc = registry.get("video_compose")
r = vc.execute({
    "operation": "render", "edit_decisions": composition,
    "asset_manifest": {"version": "1.0", "assets": []},
    "script_text": clean(full_text),
    "profile": PROFILE, "output_path": str(P / f"renders/{OUTNAME}.mp4"),
    "remotion_timeout_ms": 600000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED", f"({TOTAL}s)")
if not r.success:
    print(r.error)
    sys.exit(1)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
