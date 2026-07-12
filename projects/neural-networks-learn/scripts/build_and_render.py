"""Build edit_decisions artifact + Remotion composition and render final.mp4.

Timeline is re-timed from actual narration durations (EP narration feedback loop).
Persisted artifact is schema-valid; the enriched composition (with Remotion cut
types and flat props) is what video_compose renders — same timeline, same sources.
"""
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "neural-networks-learn"

NAVY = "#0A0E1A"
CYAN = "#22D3EE"
MAGENTA = "#E879F9"

# Assets are staged into remotion-composer/public/nn-learn/ — reference them
# with public-relative paths so Explainer's resolveAsset() routes through
# staticFile(). Remotion's <Audio> downloader rejects file:// URLs, and the
# space in "Local Sites" makes absolute-path URIs fragile for images too.
A = lambda rel: "nn-learn/" + rel.split("/")[-1]

GROK_SERIES = [
    {"label": "training accuracy", "data": [{"x": x, "y": y} for x, y in
        [(0, 12), (1, 88), (2, 99), (3, 100), (4, 100), (5, 100), (6, 100), (7, 100), (8, 100), (9, 100), (10, 100)]]},
    {"label": "test accuracy", "data": [{"x": x, "y": y} for x, y in
        [(0, 3), (1, 6), (2, 7), (3, 8), (4, 8), (5, 9), (6, 10), (7, 14), (8, 55), (9, 96), (10, 98)]]},
]

# (id, type, in, out, extra_props, artifact_fields)
CUTS = [
    ("cut-1", "line_chart", 0.0, 12.2,
     {"chartSeries": GROK_SERIES, "title": "", "xLabel": "training time", "yLabel": "accuracy",
      "chartAnimation": "draw", "chartColors": ["#155E75", MAGENTA], "showMarkers": False,
      "backgroundColor": NAVY},
     {"source": "", "reason": "scene-1 grokking chart (Remotion line_chart)"}),
    ("cut-2", None, 12.2, 17.4, {},
     {"source": "img-scene-2", "transform": {"animation": "zoom-in"},
      "reason": "scene-2 dormant network (FLUX image)"}),
    ("cut-3", None, 17.4, 26.0, {},
     {"source": "img-scene-3", "transform": {"animation": "static"},
      "reason": "scene-3 learning loop diagram (beautiful-mermaid)"}),
    ("cut-4", None, 26.0, 30.0, {},
     {"source": "img-scene-4", "transform": {"animation": "ken-burns"},
      "reason": "scene-4 backpropagation wave (FLUX image)"}),
    ("cut-5", "stat_card", 30.0, 35.0,
     {"stat": "$100,000,000+", "subtitle": "to train one frontier model — Epoch AI",
      "accentColor": CYAN, "backgroundColor": NAVY},
     {"source": "", "reason": "scene-5 training cost stat (Remotion stat_card)"}),
    ("cut-6", "stat_card", 35.0, 40.2,
     {"stat": "×2 every 5 months", "subtitle": "growth in training compute — Epoch AI",
      "accentColor": CYAN, "backgroundColor": NAVY},
     {"source": "", "reason": "scene-6 compute doubling stat (Remotion stat_card)"}),
    ("cut-7", None, 40.2, 46.5, {},
     {"source": "img-scene-7", "transform": {"animation": "zoom-in"},
      "reason": "scene-7 loss landscape (FLUX image)"}),
    ("cut-8", "line_chart", 46.5, 50.4,
     {"chartSeries": GROK_SERIES, "title": "", "xLabel": "training time", "yLabel": "accuracy",
      "chartAnimation": "draw", "chartColors": ["#155E75", MAGENTA], "showMarkers": False,
      "backgroundColor": NAVY},
     {"source": "", "reason": "scene-8 HERO grokking callback, magenta leap on 'clicks' (playbook_override: full-frame accent)"}),
    ("cut-9", None, 50.4, 55.5, {},
     {"source": "img-scene-9", "transform": {"animation": "zoom-out"},
      "reason": "scene-9 illuminated network / 2026 interpretability (FLUX image)"}),
    ("cut-10", "text_card", 55.5, 60.0,
     {"text": "Now we're learning how they learn.", "color": CYAN, "backgroundColor": NAVY},
     {"source": "", "reason": "scene-10 closing card (Remotion text_card, exact text)"}),
]

OVERLAYS = [
    {"type": "section_title", "in_seconds": 7.6, "out_seconds": 11.6, "text": "GROKKING",
     "accentColor": MAGENTA, "position": "bottom-center"},
    {"type": "section_title", "in_seconds": 17.8, "out_seconds": 21.5, "text": "THE LEARNING LOOP",
     "accentColor": CYAN, "position": "top-left"},
    {"type": "section_title", "in_seconds": 26.4, "out_seconds": 29.6, "text": "BACKPROPAGATION",
     "accentColor": CYAN, "position": "bottom-left"},
    {"type": "stat_reveal", "in_seconds": 36.2, "out_seconds": 40.0, "text": "2–3×",
     "subtitle": "cost growth per year, for 8 years", "accentColor": CYAN, "position": "bottom-right"},
    {"type": "section_title", "in_seconds": 48.0, "out_seconds": 50.4, "text": "GROKKING",
     "accentColor": MAGENTA, "position": "bottom-center"},
    {"type": "section_title", "in_seconds": 50.8, "out_seconds": 55.0, "text": "2026 — INTERPRETABILITY",
     "accentColor": CYAN, "position": "top-left"},
]

THEME = {
    "primaryColor": CYAN,
    "accentColor": MAGENTA,
    "backgroundColor": NAVY,
    "surfaceColor": "#111827",
    "textColor": "#E5F6FB",
    "mutedTextColor": "#7DD3E8",
    "headingFont": "Inter",
    "bodyFont": "Inter",
    "monoFont": "JetBrains Mono",
    "chartColors": [CYAN, MAGENTA, "#67E8F9", "#A5F3FC", "#155E75"],
    "springConfig": {"damping": 20, "stiffness": 120, "mass": 1},
    "transitionDuration": 0.4,
    "captionHighlightColor": CYAN,
    "captionBackgroundColor": "rgba(10, 14, 26, 0.75)",
}

NARRATION_STARTS = {"s1": 0.3, "s2": 12.2, "s3": 17.4, "s4": 30.0, "s5": 40.2, "s6": 50.4}

# ---------- 1. schema-valid artifact ----------
artifact_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "source": art["source"], "in_seconds": tin, "out_seconds": tout,
           "layer": "primary", "transition_in": "fade", "transition_out": "fade",
           "transition_duration": 0.4, "reason": art["reason"]}
    if "transform" in art:
        cut["transform"] = art["transform"]
    artifact_cuts.append(cut)

artifact = {
    "version": "1.0",
    "render_runtime": "remotion",
    "renderer_family": "explainer-data",
    "composition_mode": "templated",
    "cuts": artifact_cuts,
    "audio": {
        "narration": {"segments": [
            {"asset_id": f"narration-{sid}", "start_seconds": start}
            for sid, start in NARRATION_STARTS.items()]},
        "music": {"asset_id": "music-bg", "volume": 0.10,
                  "fade_in_seconds": 1.5, "fade_out_seconds": 3.0,
                  "ducking": {"enabled": True, "reduction_db": -8}},
    },
    "subtitles": {"enabled": True, "style": "word-by-word", "source": "artifacts/captions.json",
                  "font": "Inter", "position": "bottom-center"},
    "metadata": {"project_id": "neural-networks-learn", "playbook": "custom-neural-glow",
                 "target_duration_seconds": 60,
                 "notes": "Timeline re-timed from actual narration durations; composition props derived 1:1 from these cuts."},
}
schema = json.load(open(ROOT / "schemas/artifacts/edit_decisions.schema.json"))
jsonschema.validate(artifact, schema)
json.dump(artifact, open(P / "artifacts/edit_decisions.json", "w"), indent=2)
print("edit_decisions artifact: VALID")

# ---------- 2. enriched composition ----------
manifest = json.load(open(P / "artifacts/asset_manifest.json"))
lookup = {a["id"]: a["path"] for a in manifest["assets"]}
captions = json.load(open(P / "artifacts/captions.json"))

comp_cuts = []
for cid, ctype, tin, tout, props, art in CUTS:
    cut = {"id": cid, "in_seconds": tin, "out_seconds": tout,
           "transition_in": "fade", "transition_out": "fade"}
    if art["source"]:
        cut["source"] = A(lookup[art["source"]])
        cut["animation"] = art.get("transform", {}).get("animation", "ken-burns")
    else:
        cut["source"] = ""
        cut["type"] = ctype
        cut.update(props)
    comp_cuts.append(cut)

composition = {
    "version": "1.0",
    "render_runtime": "remotion",
    "renderer_family": "explainer-data",
    "composition_mode": "templated",
    "cuts": comp_cuts,
    "overlays": OVERLAYS,
    "captions": captions,
    "audio": {
        "narration": {"src": A("assets/narration/narration_full.mp3"), "volume": 1.0},
        "music": {"src": A("assets/music/background_music.mp3"), "volume": 0.10,
                  "fadeInSeconds": 1.5, "fadeOutSeconds": 3.0},
    },
    "themeConfig": THEME,
    "metadata": artifact["metadata"],
}
json.dump(composition, open(P / "artifacts/composition.json", "w"), indent=2)
print("composition written:", len(comp_cuts), "cuts,", len(OVERLAYS), "overlays,", len(captions), "caption words")

# ---------- 3. render ----------
from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
proposal = json.load(open(P / "artifacts/proposal_packet.json"))
script = json.load(open(P / "artifacts/script.json"))
script_text = " ".join(s["text"] for s in script["sections"])

r = vc.execute({
    "operation": "render",
    "edit_decisions": composition,
    "asset_manifest": manifest,
    "proposal_packet": proposal,
    "script_text": script_text,
    "profile": "youtube_landscape",
    "output_path": str(P / "renders/final.mp4"),
    "remotion_timeout_ms": 120000,
})
print("RENDER:", "SUCCESS" if r.success else "FAILED")
if not r.success:
    print(r.error)
if r.data:
    fr = r.data.get("final_review", {})
    print("final_review status:", r.data.get("final_review_status"))
    for issue in fr.get("issues_found", []):
        print("  issue:", issue)
