"""Build edit_decisions artifact + Remotion composition for the MemberIntel deep dive.

Timeline re-timed from actual narration durations (150s cut). Assets staged into
remotion-composer/public/mi-dive/ (Remotion <Audio> rejects file:// URLs).
"""
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-deep-dive"

GRAPHITE = "#0B0F14"; AMBER = "#F59E0B"; TEAL = "#2DD4BF"; GREEN = "#4ADE80"
PUB = lambda name: f"mi-dive/{name}"

GUARD_CMD = "git grep -lE '^(import anthropic|from anthropic)' -- 'src/' | grep -v 'src/memberintel/llm/'"

CUTS = [
    # (id, type-or-None, in, out, props, artifact extras)
    ("cut-1", "comparison", 0.0, 15.6,
     {"title": "the strange shape", "leftLabel": "PRODUCT CODE", "leftValue": "19,160 lines",
      "rightLabel": "TEST CODE", "rightValue": "30,867 lines", "backgroundColor": GRAPHITE,
      "cardBackgroundColor": "#121820", "textColor": "#E5F1F4", "leftColor": TEAL, "rightColor": AMBER},
     {"source": "", "reason": "scene-1 test/product comparison"}),
    ("cut-2a", None, 15.6, 19.5, {}, {"source": PUB("marketing-home.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-2a real marketing homepage screenshot"}),
    ("cut-2b", None, 19.5, 23.5, {}, {"source": PUB("app-chat-answer.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-2b real member chat with cited Sonnet 4.6 answer"}),
    ("cut-2c", None, 23.5, 27.4, {}, {"source": PUB("admin-global-brain.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-2c real Global Brain admin (email masked)"}),
    ("cut-3", None, 27.4, 32.6, {}, {"source": PUB("scene-3-gate.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-3 gate metaphor (FLUX)"}),
    ("cut-4", "terminal_scene", 32.6, 46.0,
     {"terminalTitle": "ci — guard-rules", "prompt": "ci$", "accentColor": AMBER, "steps": [
        {"kind": "cmd", "text": GUARD_CMD, "typeSpeed": 0.02},
        {"kind": "pause", "seconds": 1.2},
        {"kind": "out", "text": "(no output — zero files outside the wrapper)", "holdSeconds": 2.0},
        {"kind": "cmd", "text": "echo $?", "typeSpeed": 0.03},
        {"kind": "out", "text": "1  # grep found nothing. exactly as designed.", "holdSeconds": 1.5},
        {"kind": "pill", "text": "✓ guard-rules passed", "color": GREEN, "durationSeconds": 3.0}]},
     {"source": "", "reason": "scene-4 synthetic terminal: real CI guard grep from ci.yml"}),
    ("cut-5", "callout", 46.0, 55.9,
     {"callout_type": "info", "title": "INVARIANTS AS CI JOBS", "backgroundColor": GRAPHITE,
      "text": "anthropic  →  only llm/call.py\nmodel_id   →  read only in llm/\nstripe     →  only api/billing/\nvoyageai   →  only api/retrieval/"},
     {"source": "", "reason": "scene-5 invariant ledger (Remotion callout)"}),
    ("cut-6", "terminal_scene", 55.9, 68.5,
     {"terminalTitle": "pytest — launch-blocking evals", "prompt": "ci$", "accentColor": TEAL, "steps": [
        {"kind": "cmd", "text": "pytest tests/evals/test_tier_routing_safety.py -q", "typeSpeed": 0.03},
        {"kind": "out", "text": "iteration    1/1000 · free → claude-haiku-4-5 ✓", "holdSeconds": 1.0},
        {"kind": "out", "text": "iteration  500/1000 · free → claude-haiku-4-5 ✓", "holdSeconds": 1.0},
        {"kind": "out", "text": "iteration 1000/1000 · free → claude-haiku-4-5 ✓", "holdSeconds": 1.2},
        {"kind": "pill", "text": "PASSED — 1000/1000", "color": GREEN, "durationSeconds": 3.0}]},
     {"source": "", "reason": "scene-6 synthetic terminal: 1000-iteration eval"}),
    ("cut-7", "callout", 68.5, 76.1,
     {"callout_type": "warning", "title": "Forged handle, wrong operation", "backgroundColor": GRAPHITE,
      "text": "HandleOperationMismatch — rejected ✗\n\n9 eval suites run on every pull request."},
     {"source": "", "reason": "scene-7 forged-handle + eval-count callout"}),
    ("cut-8", "comparison", 76.1, 89.0,
     {"title": "UNIT ECONOMICS — ADR-0025", "leftLabel": "COST PER FREE USER", "leftValue": "$1.07",
      "rightLabel": "CEILING", "rightValue": "$1.10", "backgroundColor": GRAPHITE,
      "cardBackgroundColor": "#121820", "textColor": "#E5F1F4", "leftColor": TEAL, "rightColor": AMBER},
     {"source": "", "reason": "scene-8 unit economics comparison"}),
    ("cut-9", None, 89.0, 96.5, {}, {"source": PUB("scene-9-ledger-vault.png"), "transform": {"animation": "ken-burns"}, "reason": "scene-9 ledger vault (FLUX)"}),
    ("cut-10", None, 96.5, 109.5, {}, {"source": PUB("brain-quadrant.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-10 four-document brain quadrant"}),
    ("cut-11", "callout", 109.5, 118.9,
     {"callout_type": "quote", "title": "HEARTBEAT — written as prose, on purpose", "backgroundColor": GRAPHITE,
      "text": "\"142 active members, up 3 this week. MRR $4,850. Churn 2.1%, trending down.\""},
     {"source": "", "reason": "scene-11 heartbeat prose quote (exact text via Remotion)"}),
    ("cut-12", None, 118.9, 139.0, {}, {"source": PUB("persona-board.png"), "transform": {"animation": "zoom-in"}, "reason": "scene-12 persona board HERO (playbook_override: 20s hold)"}),
    ("cut-13", "comparison", 139.0, 144.0,
     {"leftLabel": "PRODUCT", "leftValue": "19,160", "rightLabel": "PROOF", "rightValue": "30,867",
      "backgroundColor": GRAPHITE, "cardBackgroundColor": "#121820", "textColor": "#E5F1F4", "leftColor": TEAL, "rightColor": AMBER},
     {"source": "", "reason": "scene-13 callback comparison"}),
    ("cut-14", "text_card", 144.0, 150.0,
     {"text": "Built paranoid, on purpose.", "color": AMBER, "backgroundColor": GRAPHITE},
     {"source": "", "reason": "scene-14 closing card"}),
]

OVERLAYS = [
    {"type": "section_title", "in_seconds": 11.0, "out_seconds": 15.4, "text": "THE PARANOID CODEBASE", "accentColor": AMBER, "position": "bottom-center"},
    {"type": "section_title", "in_seconds": 16.0, "out_seconds": 20.5, "text": "LIVE SURFACES", "accentColor": TEAL, "position": "top-left"},
    {"type": "section_title", "in_seconds": 33.2, "out_seconds": 37.5, "text": "INVARIANTS AS CI JOBS", "accentColor": AMBER, "position": "top-left"},
    {"type": "stat_reveal", "in_seconds": 50.0, "out_seconds": 55.5, "text": "4 guard rules", "subtitle": ".github/workflows/ci.yml", "accentColor": AMBER, "position": "bottom-right"},
    {"type": "section_title", "in_seconds": 56.5, "out_seconds": 60.5, "text": "LAUNCH-BLOCKING EVALS", "accentColor": AMBER, "position": "top-left"},
    {"type": "stat_reveal", "in_seconds": 91.0, "out_seconds": 96.3, "text": "-$85,000/mo", "subtitle": "one routing mistake at 50K free users", "accentColor": AMBER, "position": "bottom-right"},
    {"type": "section_title", "in_seconds": 97.2, "out_seconds": 101.5, "text": "THE CUSTOMER BRAIN — ADR-0015", "accentColor": TEAL, "position": "top-left"},
    {"type": "section_title", "in_seconds": 119.6, "out_seconds": 124.0, "text": "THE PERSONA DEV-LOOP", "accentColor": AMBER, "position": "top-left"},
]

THEME = {
    "primaryColor": TEAL, "accentColor": AMBER, "backgroundColor": GRAPHITE,
    "surfaceColor": "#121820", "textColor": "#E5F1F4", "mutedTextColor": "#8FA3AC",
    "headingFont": "JetBrains Mono", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
    "chartColors": [TEAL, AMBER, GREEN, "#93C5FD", "#F87171"],
    "springConfig": {"damping": 24, "stiffness": 140, "mass": 1},
    "transitionDuration": 0.35,
    "captionHighlightColor": AMBER,
    "captionBackgroundColor": "rgba(11, 15, 20, 0.78)",
}

NARR = {"s1": 0.3, "s2": 15.6, "s3": 32.6, "s4": 55.9, "s5": 76.1, "s6": 96.5, "s7": 118.9, "s8": 139.0}

# ---------- schema-valid artifact ----------
artifact_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "source": art["source"] if art["source"].startswith("mi-dive") else "",
           "in_seconds": tin, "out_seconds": tout, "layer": "primary",
           "transition_in": "fade", "transition_out": "fade", "transition_duration": 0.35,
           "reason": art["reason"]}
    if "transform" in art:
        cut["transform"] = art["transform"]
    artifact_cuts.append(cut)

artifact = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": artifact_cuts,
    "audio": {
        "narration": {"segments": [{"asset_id": f"narration-{s}", "start_seconds": t} for s, t in NARR.items()]},
        "music": {"asset_id": "music-bg", "volume": 0.09, "fade_in_seconds": 1.5, "fade_out_seconds": 3.5,
                  "ducking": {"enabled": True, "reduction_db": -8}},
    },
    "subtitles": {"enabled": True, "style": "word-by-word", "source": "artifacts/captions.json",
                  "font": "Inter", "position": "bottom-center"},
    "metadata": {"project_id": "memberintel-deep-dive", "playbook": "custom-guardrail-grid",
                 "target_duration_seconds": 150,
                 "notes": "Re-timed from actual narration (139.5s); 150s cut vs 165s proposal target (-9%) — narration read faster than 150wpm estimate. Real screenshots per decision d5."},
}
jsonschema.validate(artifact, json.load(open(ROOT / "schemas/artifacts/edit_decisions.schema.json")))
json.dump(artifact, open(P / "artifacts/edit_decisions.json", "w"), indent=2)
print("edit_decisions artifact: VALID")

# ---------- enriched composition ----------
captions = json.load(open(P / "artifacts/captions.json"))
comp_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "in_seconds": tin, "out_seconds": tout, "transition_in": "fade", "transition_out": "fade"}
    if art["source"]:
        cut["source"] = art["source"]
        cut["animation"] = art.get("transform", {}).get("animation", "ken-burns")
    else:
        cut["source"] = ""
        cut["type"] = ctype
        cut.update(props)
    comp_cuts.append(cut)

composition = {
    "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
    "composition_mode": "templated", "cuts": comp_cuts, "overlays": OVERLAYS, "captions": captions,
    "audio": {
        "narration": {"src": "mi-dive/narration_full.mp3", "volume": 1.0},
        "music": {"src": "mi-dive/background_music.mp3", "volume": 0.09, "fadeInSeconds": 1.5, "fadeOutSeconds": 3.5},
    },
    "themeConfig": THEME, "metadata": artifact["metadata"],
}
json.dump(composition, open(P / "artifacts/composition.json", "w"), indent=2)
print(f"composition: {len(comp_cuts)} cuts, {len(OVERLAYS)} overlays, {len(captions)} caption words")

# ---------- render ----------
from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
manifest_assets = []
for cid, ctype, tin, tout, props, art in CUTS:
    if art["source"]:
        manifest_assets.append({"id": cid + "-img", "type": "image", "path": art["source"],
                                "source_tool": "staged", "scene_id": cid})
minimal_manifest = {"version": "1.0", "assets": manifest_assets}
proposal = json.load(open(P / "artifacts/proposal_packet.json"))
script = json.load(open(P / "artifacts/script.json"))
r = vc.execute({
    "operation": "render",
    "edit_decisions": composition,
    "asset_manifest": minimal_manifest,
    "proposal_packet": proposal,
    "script_text": " ".join(s["text"] for s in script["sections"]),
    "profile": "youtube_landscape",
    "output_path": str(P / "renders/final.mp4"),
    # Lifts both Remotion's own --timeout and the tool's subprocess cap
    # (subprocess_timeout = ms/1000 + 60). A 150s/1080p render needs ~10 min here.
    "remotion_timeout_ms": 1200000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED")
if not r.success:
    print(r.error)
elif r.data:
    print("final_review:", r.data.get("final_review_status"))
