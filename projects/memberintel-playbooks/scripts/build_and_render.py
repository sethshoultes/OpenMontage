"""Batch-build + render the 3 playbook spotlight pilots (landscape, dynamic timelines)."""
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
P = ROOT / "projects" / "memberintel-playbooks"
PUBDIR = ROOT / "remotion-composer/public/mi-brains"
subprocess.run(["cp", str(P / "assets/music/series_bed.mp3"), str(PUBDIR / "pb_music.mp3")], check=True)

BG = "#FAFBFC"; NAVY = "#0F172A"; TEAL = "#0EA5A0"
PUB = lambda n: f"mi-brains/{n}"

def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())

from tools.tool_registry import registry
registry.discover()
vc = registry.get("video_compose")
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")

proposal = json.load(open(ROOT / "projects/memberintel-teaser/artifacts/proposal_packet.json"))
series = json.load(open(P / "artifacts/series_data.json"))
results = {}

for vid, meta in series.items():
    parts = ["hook", "insight", "cta"]
    D = {p: dur(P / f"assets/narration/{vid}-{p}.mp3") for p in parts}
    LEAD, GAP, TAIL = 1.2, 0.7, 3.5
    NARR = {}
    t = LEAD
    for p in parts:
        NARR[p] = round(t, 2)
        t += D[p] + GAP
    TOTAL = round(t - GAP + TAIL, 2)

    # assemble narration
    inputs, filters = [], []
    for i, p in enumerate(parts):
        inputs += ["-i", str(P / f"assets/narration/{vid}-{p}.mp3")]
        ms = int(NARR[p] * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(parts)))
    fc = ";".join(filters) + f";{mix}amix=inputs={len(parts)}:normalize=0,apad=whole_dur={TOTAL}[out]"
    narr_path = P / f"assets/narration/{vid}-full.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                    "-c:a", "libmp3lame", "-q:a", "2", str(narr_path)], check=True)
    subprocess.run(["cp", str(narr_path), str(PUBDIR / f"{vid}_narration.mp3")], check=True)

    segments, _ = model.transcribe(str(narr_path), word_timestamps=True, language="en")
    captions = []
    for seg in segments:
        for w in seg.words or []:
            captions.append({"word": w.word.strip(), "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})

    # scenes: question card (hook window), insight cards 1+2 (split insight window), CTA card
    hook_end = NARR["insight"]
    ins_end = NARR["cta"]
    mid = round(NARR["insight"] + (ins_end - NARR["insight"]) * 0.5, 2)
    cuts = [
        {"id": "c1", "source": PUB(f"{vid}-q.png"), "animation": "zoom-in", "in_seconds": 0.0, "out_seconds": hook_end, "transition_in": "fade", "transition_out": "fade"},
        {"id": "c2", "source": PUB(f"{vid}-c1.png"), "animation": "zoom-in", "in_seconds": hook_end, "out_seconds": mid, "transition_in": "fade", "transition_out": "fade"},
        {"id": "c3", "source": PUB(f"{vid}-c2.png"), "animation": "zoom-in", "in_seconds": mid, "out_seconds": ins_end, "transition_in": "fade", "transition_out": "fade"},
        {"id": "c4", "source": PUB("pb-cta.png"), "animation": "static", "in_seconds": ins_end, "out_seconds": TOTAL, "transition_in": "fade", "transition_out": "fade"},
    ]
    composition = {
        "version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data",
        "composition_mode": "templated", "cuts": cuts, "overlays": [], "captions": captions,
        "audio": {
            "narration": {"src": PUB(f"{vid}_narration.mp3"), "volume": 1.0},
            "music": {"src": PUB("pb_music.mp3"), "volume": 0.12, "fadeInSeconds": 0.5, "fadeOutSeconds": 1.5},
        },
        "themeConfig": {
            "primaryColor": meta["accent"], "accentColor": meta["accent"], "backgroundColor": BG,
            "surfaceColor": "#FFFFFF", "textColor": NAVY, "mutedTextColor": "#64748B",
            "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
            "chartColors": [meta["accent"], NAVY, TEAL],
            "springConfig": {"damping": 22, "stiffness": 150, "mass": 1},
            "transitionDuration": 0.35,
            "captionHighlightColor": meta["accent"], "captionTextColor": NAVY,
            "captionBackgroundColor": "rgba(255, 255, 255, 0.88)",
        },
        "metadata": {"project_id": "memberintel-playbooks", "video": vid, "target_duration_seconds": TOTAL,
                     "notes": f"Playbook spotlight pilot {vid}; script derived from team-reviewed playbook."},
    }
    manifest = {"version": "1.0", "assets": [
        {"id": c["id"] + "-img", "type": "image", "path": c["source"], "source_tool": "staged", "scene_id": c["id"]}
        for c in cuts]}
    r = vc.execute({
        "operation": "render", "edit_decisions": composition, "asset_manifest": manifest,
        "proposal_packet": proposal,
        "script_text": meta["hook"] + " " + meta["insight"],
        "profile": "youtube_landscape", "output_path": str(P / f"renders/{vid}.mp4"),
        "remotion_timeout_ms": 600000,
    })
    results[vid] = {"success": r.success, "total": TOTAL,
                    "review": (r.data or {}).get("final_review_status") if r.success else r.error}
    print(vid, "->", "OK" if r.success else "FAILED", TOTAL, "s", results[vid]["review"])

json.dump(results, open(P / "artifacts/batch_results.json", "w"), indent=2)
print("BATCH DONE:", all(v["success"] for v in results.values()))
