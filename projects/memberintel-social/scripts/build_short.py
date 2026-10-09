"""Two-host vertical short builder — one episode JSON in, one 9:16 mp4 out.

Usage: build_short.py <episode.json> [profile]

Episode JSON:
{
  "output": "data-drop-01",
  "lines": [
    {"s": "W"|"M", "text": "[tag] spoken line...",
     "punch": {  # optional card that takes the back ~55% of the line
        "type": "text_card"|"stat_card"|"comparison",
        "bg": "bg-name.png",              # art behind the card (assets/)
        ...type-specific fields...
     }},
  ],
  "end": {"text": "Series Name", "subtitle": "...", "bg": "bg-brand.png"}
}

Per-line eleven_v3 TTS (two voices, tight gaps) gives an exact per-speaker
timeline; each line cuts to the active host's portrait, punch cards split
the big lines. Line audio is cached per episode, so re-renders keep takes.
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
P = ROOT / "projects" / "memberintel-social"
PUBDIR = ROOT / "remotion-composer/public/mi-social"
PUBDIR.mkdir(parents=True, exist_ok=True)
PUB = lambda n: f"mi-social/{n}"
(P / "assets/narration").mkdir(parents=True, exist_ok=True)
(P / "artifacts").mkdir(exist_ok=True)
(P / "renders").mkdir(exist_ok=True)

INK = "#0B0F14"; PAPER = "#F8FAFC"; TEAL = "#2DD4BF"; ORANGE = "#F97316"
VOICES = {"W": "h2OBoQqre8SPfGehinER",  # Nova: Melanie (2026-10-02 lead ruling; was Tiffany, now Nadia's alone)
          "M": "1SM7GgM6IMuvQlz2BwM3",
          "S": "J8hhQxHTArNAtWDmol2o"}  # Seth (guest)
AVATAR = {"W": "host-w.png", "M": "host-m.png", "S": "host-s.png"}

EP = json.load(open(sys.argv[1]))
DEFAULT_PROFILE = EP.get("profile", "youtube_shorts")
PROFILE = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROFILE
OUTNAME = EP["output"]  # identity for TTS/art caches — stays constant across aspect ratios
# Final mp4/artifact name: unsuffixed for the episode's own default aspect,
# so existing slugs never move; a CLI-requested OTHER aspect gets a suffix
# so it can coexist as a companion file (e.g. a landscape cut for blog use).
RENDER_NAME = OUTNAME if PROFILE == DEFAULT_PROFILE else (
    f"{OUTNAME}-landscape" if PROFILE == "youtube_landscape" else f"{OUTNAME}-portrait")
LINES = EP["lines"]
OUT = P / f"renders/{RENDER_NAME}.mp4"


def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


# stage avatars + generated backgrounds into public/
for img in sorted((P / "assets").glob("*.png")):
    subprocess.run(["cp", str(img), str(PUBDIR / img.name)], check=True)

from tools.tool_registry import registry
registry.discover()
tts = registry.get("tts_selector")

# per-line TTS: exact per-speaker timing beats one-take here — the visuals
# cut on speaker turns, and rapid banter hides the seams a monologue can't
for i, ln in enumerate(LINES):
    key = hashlib.md5((ln["s"] + "|" + ln["text"]).encode()).hexdigest()[:8]
    out = P / f"assets/narration/{OUTNAME}-line-{i:02d}-{key}.mp3"
    plain = re.sub(r"\[[^\]]+\]\s*", "", ln["text"])
    if out.exists() and out.stat().st_size > 1000:
        ln["dur"] = dur(out)
        print(f"line {i:02d} [{ln['s']}] {ln['dur']:.2f}s (cached)")
        continue
    r = tts.execute({"text": ln["text"], "preferred_provider": "elevenlabs",
        "voice_id": VOICES[ln["s"]], "model_id": "eleven_v3",
        "stability": 0.50, "similarity_boost": 0.85,
        "output_path": str(out)})
    if not r.success:
        print(f"line {i} v3 failed ({r.error}); falling back to multilingual_v2")
        r = tts.execute({"text": plain, "preferred_provider": "elevenlabs",
            "voice_id": VOICES[ln["s"]], "model_id": "eleven_multilingual_v2",
            "stability": 0.50, "similarity_boost": 0.85, "style": 0.35, "speed": 1.05,
            "output_path": str(out)})
        assert r.success, r.error
    ln["dur"] = dur(out)
    print(f"line {i:02d} [{ln['s']}] {ln['dur']:.2f}s")

LEAD, GAP, TAIL = 0.7, 0.15, 2.4
t = LEAD
for ln in LINES:
    ln["t0"] = round(t, 2)
    t += ln["dur"] + GAP
LAST_END = round(t - GAP, 2)
TOTAL = round(LAST_END + TAIL, 2)
print(f"timeline: {TOTAL}s")

inputs, filters = [], []
for i, ln in enumerate(LINES):
    key = hashlib.md5((ln["s"] + "|" + ln["text"]).encode()).hexdigest()[:8]
    inputs += ["-i", str(P / f"assets/narration/{OUTNAME}-line-{i:02d}-{key}.mp3")]
    ms = int(ln["t0"] * 1000)
    filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(LINES)))
fc = ";".join(filters) + f";{mix}amix=inputs={len(LINES)}:normalize=0,apad=whole_dur={TOTAL}[out]"
narr = P / f"assets/narration/{OUTNAME}-full.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2", str(narr)], check=True)
subprocess.run(["cp", str(narr), str(PUBDIR / f"{OUTNAME}_narration.mp3")], check=True)

bed = PUBDIR / "social_bed.mp3"
if not bed.exists() or dur(bed) < TOTAL:
    music = registry.get("music_gen")
    r = music.execute({
        "prompt": "High-energy modern tech beat, punchy percussion, bright synth stabs, upbeat social media edit, driving, loops well, instrumental only",
        "duration_seconds": int(TOTAL) + 2, "output_path": str(bed)})
    assert r.success, r.error

from faster_whisper import WhisperModel
from tools.subtitle.caption_align import align_words_to_reference
model = WhisperModel("base", device="cpu", compute_type="int8")

# Per-line, not one pass over the full mix: Whisper's own transcribed TEXT is
# only used to recover per-word TIMING (via align_words_to_reference below).
# The caption WORDS themselves always come from the line's own script text —
# already correct by construction, since it's what was fed to TTS — so a
# brand/product term Whisper mis-hears (e.g. "MembersIntel") can never land
# in a caption misspelled; the timing estimate for it just gets interpolated
# from its neighbors instead.
captions = []
for i, ln in enumerate(LINES):
    key = hashlib.md5((ln["s"] + "|" + ln["text"]).encode()).hexdigest()[:8]
    clip = P / f"assets/narration/{OUTNAME}-line-{i:02d}-{key}.mp3"
    reference_words = re.sub(r"\[[^\]]+\]\s*", "", ln["text"]).split()
    if not reference_words:
        continue
    segments, _ = model.transcribe(str(clip), word_timestamps=True, language="en")
    whisper_words = [(w.word.strip(), w.start, w.end) for seg in segments for w in (seg.words or [])]
    if whisper_words:
        aligned = align_words_to_reference(whisper_words, reference_words)
    else:
        # No usable ASR signal for this clip (silent/failed) — spread the
        # line's own known duration evenly. Still spelling-correct, just
        # without natural per-word pacing.
        step = ln["dur"] / len(reference_words)
        aligned = [(w, k * step, (k + 1) * step) for k, w in enumerate(reference_words)]
    for word, start_s, end_s in aligned:
        captions.append({"word": word, "startMs": int((ln["t0"] + start_s) * 1000),
                          "endMs": int((ln["t0"] + end_s) * 1000)})

# Captions never burn into the picture (Seth, 2026-10-08): the word timing
# ships as a SubRip sidecar next to the mp4, for upload as a caption track.
def srt_time(ms):
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


cues = []
for w in captions:
    cue = cues[-1] if cues else None
    if cue is None or len(cue) >= 6 or w["endMs"] - cue[0]["startMs"] > 2500:
        cues.append([w])
    else:
        cue.append(w)
SRT = OUT.with_suffix(".srt")
SRT.write_text("".join(
    f"{n}\n{srt_time(c[0]['startMs'])} --> {srt_time(c[-1]['endMs'])}\n{' '.join(w['word'] for w in c)}\n\n"
    for n, c in enumerate(cues, 1)))
print(len(captions), "caption words ->", SRT.name)

# cuts: one avatar scene per line; punch cards take the back ~55% of flagged
# lines (minimum 1.6s or no split)
CUTS = []
for i, ln in enumerate(LINES):
    end = LINES[i + 1]["t0"] if i + 1 < len(LINES) else LAST_END
    start = ln["t0"] if i > 0 else 0.0
    punch = ln.get("punch")
    split = round(start + (end - start) * 0.45, 2) if punch and (end - start) * 0.55 >= 1.6 else None
    CUTS.append({"id": f"l{i:02d}", "source": "", "type": "anime_scene",
                 "images": [PUB(AVATAR[ln["s"]])], "particles": False, "vignette": True,
                 "in_seconds": start, "out_seconds": split or end,
                 "transition_in": "fade", "transition_out": "fade",
                 # Avatars are portrait-shaped (768x1344); a landscape canvas
                 # would "cover"-crop to the middle ~32% of the image height
                 # and the camera pan can push the face off-frame. Letterbox
                 # with a blurred backdrop instead when rendering landscape.
                 **({"fit": "contain-blurred"} if PROFILE == "youtube_landscape" else {})})
    if split:
        card = {"id": f"p{i:02d}", "source": "", "in_seconds": split, "out_seconds": end,
                "transition_in": "fade", "transition_out": "fade", "backgroundColor": INK,
                "backgroundImage": PUB(punch["bg"]), "backgroundOverlay": punch.get("overlay", 0.42)}
        if punch["type"] == "stat_card":
            card.update({"type": "stat_card", "stat": punch["stat"], "subtitle": punch["subtitle"],
                         "accentColor": ORANGE})
        elif punch["type"] == "comparison":
            card.update({"type": "comparison", "title": punch.get("title"),
                         "leftLabel": punch["leftLabel"], "leftValue": punch["leftValue"],
                         "rightLabel": punch["rightLabel"], "rightValue": punch["rightValue"],
                         "leftColor": punch.get("leftColor", "#94A3B8"),
                         "rightColor": punch.get("rightColor", TEAL),
                         "cardBackgroundColor": "rgba(17, 24, 39, 0.88)", "color": PAPER})
        else:
            card.update({"type": "text_card", "text": punch["text"], "color": PAPER,
                         "fontSize": punch.get("fontSize", 72)})
        CUTS.append(card)
END = EP["end"]
CUTS.append({"id": "end", "source": "", "type": "hero_title", "text": END["text"],
             "heroSubtitle": END.get("subtitle"), "backgroundColor": INK,
             "backgroundImage": PUB(END.get("bg", "bg-brand.png")), "backgroundOverlay": 0.35,
             "in_seconds": LAST_END, "out_seconds": TOTAL,
             "transition_in": "fade", "transition_out": "fade"})

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [], "captions": [],
    "audio": {
        "narration": {"src": PUB(f"{OUTNAME}_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("social_bed.mp3"), "volume": 0.13, "fadeInSeconds": 0.3, "fadeOutSeconds": 1.5},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": ORANGE, "backgroundColor": INK,
        "surfaceColor": "#111827", "textColor": PAPER, "mutedTextColor": "#94A3B8",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, ORANGE, PAPER],
        "springConfig": {"damping": 16, "stiffness": 220, "mass": 0.8},
        "transitionDuration": 0.2,
    },
    "metadata": {"project_id": "memberintel-social", "video": OUTNAME,
                 "target_duration_seconds": TOTAL,
                 "notes": "Two-host vertical short; per-line v3 dialogue, punch cards."},
}
json.dump(composition, open(P / f"artifacts/{OUTNAME}-composition.json", "w"), indent=2)

vc = registry.get("video_compose")
proposal = json.load(open(ROOT / "projects/memberintel-brains/artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition,
    "asset_manifest": {"version": "1.0", "assets": []},
    "proposal_packet": proposal,
    "script_text": " ".join(re.sub(r"\[[^\]]+\]\s*", "", ln["text"]) for ln in LINES),
    "profile": PROFILE, "output_path": str(OUT),
    "remotion_timeout_ms": 600000,
})
if not r.success:
    print("RENDER FAILED:", r.error)
    sys.exit(1)
print("RENDER OK", f"{TOTAL}s ->", OUT)
