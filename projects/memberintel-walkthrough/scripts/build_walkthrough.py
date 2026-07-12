"""MembersIntel product walkthrough — ~95s landscape, real staging captures.

Usage: build_walkthrough.py

Single-take Seth narration (eleven_v3, tags), whisper-anchored cuts through
the sanitized frames in assets/frames/. The three email beats render as
branded inbox cards UNLESS a real capture exists (03-email-welcome-verify.png,
10b-email-synced-adventurebuildr.png, 16-email-synced-801website.png) — drop those in
and re-run to upgrade. Source: ~/projects/memberintel-245-walkthrough.
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
P = ROOT / "projects" / "memberintel-walkthrough"
PUBDIR = ROOT / "remotion-composer/public/mi-walkthrough"
PUBDIR.mkdir(parents=True, exist_ok=True)
PUB = lambda n: f"mi-walkthrough/{n}"
(P / "assets/narration").mkdir(parents=True, exist_ok=True)

BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"; ORANGE = "#F97316"
VOICE = os.environ.get("SETH_VOICE_ID", "J8hhQxHTArNAtWDmol2o")
OUTNAME = "walkthrough-v1"

NARRATION = (
    "[warm] Let me walk you through MembersIntel — from zero to real answers in about two "
    "minutes. And this is the actual product, running on a real site. You sign up in "
    "seconds — no card required to start. You'll get a welcome note from Blair, our CEO... "
    "one click, and your email's verified. Going pro is a single screen: twenty-nine a "
    "month, billed securely through Stripe. [casually] And just like that, you're Pro. Now "
    "let's connect your data. Connect your MemberPress site — sign in through the plugin in "
    "two clicks, or paste an API key. The first sync runs in seconds... and a recap lands "
    "in your inbox: your members, your revenue, your churn — all live. Your dashboard "
    "lights up with real numbers. [warm] And then, you just ask. MembersIntel reads your "
    "live data and cites every claim it makes — real answers from your site, with sources. "
    "Running more than one site? Add each one for ten a month — confirmed up front, no "
    "surprises. Every new site syncs and recaps the same way. [warm] That's MembersIntel. "
    "Connect your site, and start asking."
)

def email_or_card(img_name, title, text):
    """Real Gmail capture if present, branded inbox card otherwise."""
    if (P / "assets/frames" / img_name).exists():
        return {"type": "frame", "img": img_name}
    return {"type": "card", "title": title, "text": text}

# (scene, anchor phrase | None for the opener)
SCENES = [
    ({"type": "frame", "img": "01-marketing-home.png"}, None),
    ({"type": "frame", "img": "02-register.png"}, "sign up in seconds"),
    (email_or_card("03-email-welcome-verify.png", "In your inbox",
                   "A welcome from Blair, our CEO —\nwhat happens next, in plain English."), "welcome note from"),
    ({"type": "frame", "img": "06-email-verified.png"}, "one click and"),
    ({"type": "frame", "img": "05-stripe-checkout.png"}, "going pro is"),
    ({"type": "frame", "img": "07-pro-settings.png"}, "just like that"),
    ({"type": "frame", "img": "08-connect-manual.png"}, "connect your memberpress"),
    ({"type": "frame", "img": "10-synced.png"}, "first sync runs"),
    (email_or_card("10b-email-synced-adventurebuildr.png", "In your inbox",
                   "You're connected — first sync done.\nMembers, revenue, churn: live."), "recap lands in"),
    ({"type": "frame", "img": "11-dashboard-live.png"}, "dashboard lights up"),
    ({"type": "frame", "img": "12-chat-intro.png"}, "then you just ask"),
    ({"type": "frame", "img": "13-chat-live-answer.png"}, "reads your live"),
    ({"type": "frame", "img": "14-addon-padded.png"}, "running more than"),
    ({"type": "frame", "img": "15-two-sites.png"}, "every new site"),
    (email_or_card("16-email-synced-801website.png", "In your inbox",
                   "801website.com — sync done.\n22 members · $28 MRR, live."), "syncs and recaps"),
    ({"type": "end"}, "connect your site and"),
]

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

for img in sorted((P / "assets/frames").glob("*.png")):
    subprocess.run(["cp", str(img), str(PUBDIR / img.name)], check=True)

from tools.tool_registry import registry
registry.discover()
tts = registry.get("tts_selector")
raw = P / f"assets/narration/{OUTNAME}-raw.mp3"
PLAIN = re.sub(r"\[[^\]]+\]\s*", "", NARRATION)
import hashlib
_key = P / f"assets/narration/{OUTNAME}-raw.key"
_want = hashlib.md5(NARRATION.encode()).hexdigest()
if raw.exists() and _key.exists() and _key.read_text() == _want:
    print("narration cached — reusing take")
    r = type("R", (), {"success": True})()
else:
    _key.write_text(_want)
    r = tts.execute({"text": NARRATION, "preferred_provider": "elevenlabs",
        "voice_id": VOICE, "model_id": "eleven_v3",
        "stability": 0.50, "similarity_boost": 0.85, "output_path": str(raw)})
if not r.success:
    print(f"v3 failed ({r.error}); falling back")
    r = tts.execute({"text": PLAIN, "preferred_provider": "elevenlabs",
        "voice_id": VOICE, "model_id": "eleven_multilingual_v2",
        "stability": 0.50, "similarity_boost": 0.85, "style": 0.30, "speed": 1.0,
        "output_path": str(raw)})
    assert r.success, r.error
NARR_DUR = dur(raw)
print(f"narration: {NARR_DUR:.1f}s")

LEAD, TAIL = 1.0, 2.8
TOTAL = round(LEAD + NARR_DUR + TAIL, 2)
narr = P / f"assets/narration/{OUTNAME}-full.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
                "-filter_complex", f"adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad=whole_dur={TOTAL}",
                "-c:a", "libmp3lame", "-q:a", "2", str(narr)], check=True)
subprocess.run(["cp", str(narr), str(PUBDIR / f"{OUTNAME}_narration.mp3")], check=True)

bed = PUBDIR / "walkthrough_bed.mp3"
if not bed.exists() or dur(bed) < TOTAL:
    music = registry.get("music_gen")
    r = music.execute({
        "prompt": "Warm optimistic product-demo score, light plucks and soft pulse, friendly, modern, understated, loops well, instrumental only",
        "duration_seconds": int(TOTAL) + 2, "output_path": str(bed)})
    assert r.success, r.error

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

NUM_WORDS = {"one": "1", "two": "2", "ten": "10", "nine": "9"}
def norm(tok):
    t = tok.strip(".,!?…:;").lower()
    return NUM_WORDS.get(t, t)
def tok_match(t, w):
    return t == w or (len(t) >= 3 and t.isalpha() and w.startswith(t))
def anchor_time(phrase, default, start=0):
    target = [norm(t) for tok in phrase.split() for t in re.split(r"[-–]", tok) if t]
    for i in range(start, len(words) - len(target) + 1):
        if all(tok_match(target[j], norm(words[i + j][0])) for j in range(len(target))):
            return round(max(0.0, words[i][1] - 0.15), 2), i + len(target)
    print(f"WARN anchor not found: {phrase!r}, default {default}")
    return default, start

# sequential anchor pass; a missed anchor falls back to an even split later
times = [0.0]
idx = 0
for n, (_, anchor) in enumerate(SCENES[1:], start=1):
    t, idx = anchor_time(anchor, None, idx)
    times.append(t)
# fill misses by interpolating between known neighbours
for n in range(1, len(times)):
    if times[n] is None:
        nxt = next((times[m] for m in range(n + 1, len(times)) if times[m] is not None), TOTAL - 3)
        prv = times[n - 1]
        times[n] = round(prv + (nxt - prv) / 2, 2)
# enforce a 1.2s minimum scene length
for n in range(1, len(times)):
    times[n] = max(times[n], round(times[n - 1] + 1.2, 2))
print("cuts:", times)

CUTS = []
for n, (scene, _) in enumerate(SCENES):
    start = times[n]
    end = times[n + 1] if n + 1 < len(SCENES) else TOTAL
    base = {"id": f"s{n:02d}", "source": "", "in_seconds": start, "out_seconds": end,
            "transition_in": "fade", "transition_out": "fade"}
    if scene["type"] == "frame":
        base.update({"type": "anime_scene", "images": [PUB(scene["img"])],
                     "particles": False, "vignette": False})
    elif scene["type"] == "card":
        base.update({"type": "callout", "callout_type": "info", "title": scene["title"],
                     "text": scene["text"], "backgroundColor": BG})
    else:
        base.update({"type": "hero_title", "text": "MembersIntel",
                     "heroSubtitle": "connect your site, and start asking", "backgroundColor": BG})
    CUTS.append(base)

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": CUTS, "overlays": [], "captions": captions,
    "audio": {
        "narration": {"src": PUB(f"{OUTNAME}_narration.mp3"), "volume": 1.0},
        "music": {"src": PUB("walkthrough_bed.mp3"), "volume": 0.09, "fadeInSeconds": 0.5, "fadeOutSeconds": 2.0},
    },
    "themeConfig": {
        "primaryColor": TEAL, "accentColor": ORANGE, "backgroundColor": BG,
        "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
        "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
        "chartColors": [TEAL, NAVY, ORANGE],
        "springConfig": {"damping": 22, "stiffness": 150, "mass": 1},
        "transitionDuration": 0.3,
        "captionHighlightColor": TEAL, "captionTextColor": NAVY,
        "captionBackgroundColor": "rgba(255, 255, 255, 0.9)",
    },
    "metadata": {"project_id": "memberintel-walkthrough", "video": OUTNAME,
                 "target_duration_seconds": TOTAL,
                 "notes": "Product walkthrough from staging captures (memberintel-245-walkthrough handoff)."},
}
json.dump(composition, open(P / f"artifacts/{OUTNAME}-composition.json", "w"), indent=2)

vc = registry.get("video_compose")
proposal = json.load(open(ROOT / "projects/memberintel-brains/artifacts/proposal_packet.json"))
r = vc.execute({
    "operation": "render", "edit_decisions": composition,
    "asset_manifest": {"version": "1.0", "assets": []},
    "proposal_packet": proposal, "script_text": PLAIN,
    "profile": "youtube_landscape", "output_path": str(P / f"renders/{OUTNAME}.mp4"),
    "remotion_timeout_ms": 900000,
})
if not r.success:
    print("RENDER FAILED:", r.error)
    sys.exit(1)
print("RENDER OK", f"{TOTAL}s ->", P / f"renders/{OUTNAME}.mp4")
