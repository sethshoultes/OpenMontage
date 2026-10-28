"""One sethshoultes.com page URL in, one 45-90 second SEO video out (sethshoultes.github.io#145).

Usage: build_page_video.py <page-url> [--plan-only]
Env:   ELEVENLABS_API_KEY (source ~/.config/dev-secrets/secrets.env)
Out:   projects/seo-page-videos/renders/<slug>.mp4, <slug>.srt (YouTube caption track, never burned in),
       <slug>.youtube.json (title, description with the page link, tags, chapters)

The video is a list of beats. A beat is a card on screen and the line spoken while it is up, so the picture
always matches the voice: title card over the intro, then per page section a silent heading card and one
beat per point, then the end card (the page's own image sits behind a section's cards when it has one).
Beats come from the page's own sentences, or from scripts/pages/<slug>.json when a page has hand-written
ones. The voice is Seth's ElevenLabs clone (config.json, the one place the voice id lives). Captions are cut
from the script text, not recognised from the audio. --plan-only prints the beats without spending anything.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
P = ROOT / "projects/seo-page-videos"
CFG = json.load(open(P / "scripts/config.json"))
T = CFG["theme"]
SKIP_HEADING = re.compile(r"else i do|where i work|question|straight answers|related|more from", re.I)


class Page(HTMLParser):
    """h1, meta description, then the sections under each h2: paragraphs, list items, content images."""

    def __init__(self):
        super().__init__()
        self.title, self.desc, self.lede = "", "", ""
        self.sections, self.cur, self.tag, self.buf = [], None, None, ""
        self.in_main = self.in_nav = 0

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content", "")
        if tag in ("nav", "header", "footer"):
            self.in_nav += 1
        if tag in ("h1", "h2", "h3", "p", "li"):
            self.tag, self.buf = tag, ""
        if tag == "img" and self.cur is not None and not self.in_nav and a.get("src"):
            self.cur["images"].append(a["src"])

    def handle_endtag(self, tag):
        if tag in ("nav", "header", "footer"):
            self.in_nav = max(0, self.in_nav - 1)
        if tag != self.tag:
            return
        text = re.sub(r"\s+", " ", self.buf).strip()
        self.tag = None
        if not text or self.in_nav and tag != "h1":
            return
        if tag == "h1":
            self.title = text
            self.cur = {"heading": "", "paras": [], "items": [], "images": []}  # the lede, under the h1
            self.sections.append(self.cur)
        elif tag == "h2":
            self.cur = {"heading": text, "paras": [], "items": [], "images": []}
            self.sections.append(self.cur)
        elif self.cur is not None and tag == "p":
            self.cur["paras"].append(text)
        elif self.cur is not None and tag == "li":
            self.cur["items"].append(text)

    def handle_data(self, d):
        if self.tag:
            self.buf += d


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def short(text, n=64):
    """A point for the screen: the first sentence, cut at its first comma when long, never with an ellipsis."""
    first = sentences(text)[0].rstrip(".")
    if len(first) > n and ", " in first and len(first.split(", ")[0]) >= 30:
        first = first.split(", ")[0]
    return first


def plan(url):
    html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "seo-page-videos"}), timeout=30).read().decode()
    pg = Page()
    pg.feed(html)
    lede, rest = pg.sections[0], pg.sections[1:]
    body = [s for s in rest if s["paras"] and not SKIP_HEADING.search(s["heading"])][: CFG["max_sections"]]
    title = re.split(r"[:|]", pg.title)[0].strip()
    intro = " ".join(sentences(" ".join(lede["paras"]) or pg.desc)[:2])
    slug = urlparse(url).path.strip("/").replace("/", "-") or "home"
    ov = Path(__file__).parent / "pages" / f"{slug}.json"  # optional hand-written beats, by section heading
    override = json.load(open(ov))["beats"] if ov.exists() else {}
    scenes = []
    for s in body:
        paras = [p for p in s["paras"] if len(p.split()) > 2]
        auto = [{"card": short(x), "say": x} for x in sentences(paras[0])[:2]]
        scenes.append({"heading": s["heading"], "beats": override.get(s["heading"]) or auto,
                       "image": urljoin(url, s["images"][0]) if s["images"] else None})
    ov_io = override.get("_intro_outro", {})
    return {"url": url, "title": title, "desc": pg.desc, "scenes": scenes,
            "intro": ov_io.get("intro") or intro,
            "outro": ov_io.get("outro") or {"say": f"Want to talk it through? Book a call at {CFG['site'].replace('.', ' dot ')}.",
                                           "caption": f"Want to talk it through? Book a call at {CFG['site']}."}}


def build_background(src_dir, out, total, orb_at):
    """Flow clips, trimmed and crossfaded, up to the end card; then the orb forming, landing as the end card opens."""
    XF = 1.0
    flow = [src_dir / "flow-idle.webm", src_dir / "flow-sweep.webm"]
    assert all(f.exists() for f in flow + [src_dir / "orb-form.webm"]), f"record the loops first: bg/record_flow_bg.mjs -> {src_dir}"
    SEG = 13.0  # seconds taken from each loop (1.5s in, to skip the mount)
    n, cover = 0, 0.0
    while cover < orb_at + XF:
        cover += SEG - (XF if n else 0)
        n += 1
    ins, fc = [], []
    for i in range(n):
        ins += ["-ss", "1.5", "-t", str(SEG), "-i", str(flow[i % 2])]
        fc.append(f"[{i}:v]fps=30,scale=1920:1080,format=yuv420p,setpts=PTS-STARTPTS[v{i}]")
    ins += ["-ss", "5.5", "-i", str(src_dir / "orb-form.webm")]
    # the orb clip is shrunk to 85% and shifted right so the end card's text sits in clear space on the left
    fc.append(f"[{n}:v]fps=30,scale=1632:918,pad=1920:1080:288:81:color=0x0b0d10,format=yuv420p,setpts=PTS-STARTPTS[v{n}]")
    chain, last, t = None, "v0", SEG
    for i in range(1, n):
        off = round(t - XF, 2)
        fc.append(f"[{last}][v{i}]xfade=transition=fade:duration={XF}:offset={off}[x{i}]")
        last, t = f"x{i}", t + SEG - XF
    # the flow ends where the orb begins: cut the flow at orb_at + XF, crossfade into the orb clip
    fc.append(f"[{last}]trim=duration={orb_at:.2f},setpts=PTS-STARTPTS[fl]")
    fc.append(f"[fl][v{n}]xfade=transition=fade:duration={XF}:offset={orb_at - XF:.2f}[all]")
    fc.append(f"[all]trim=duration={total:.2f},setpts=PTS-STARTPTS[o]")
    subprocess.run(["nice", "ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[o]", "-an",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30", str(out)], check=True)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def srt_time(ms):
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main(url, plan_only):
    pl = plan(url)
    slug = urlparse(url).path.strip("/").replace("/", "-") or "home"
    # beats: (key, card text, spoken line or None for a silent card, caption text, section number, card colour/size)
    beats = [("intro", pl["title"], pl["intro"], pl["intro"], 0, (T["accent"], 110))]
    for n, sc in enumerate(pl["scenes"], 1):
        beats.append((f"h{n}", sc["heading"], None, None, n, (T["accent"], 100)))
        beats += [(f"b{n}-{i}", b["card"], b["say"], b["say"], n, (T["text"], 100)) for i, b in enumerate(sc["beats"])]
    beats.append(("outro", f"{CFG['site']}  ·  {CFG['cta']}", pl["outro"]["say"], pl["outro"]["caption"], 0, (T["text"], 76)))
    words = sum(len((b[2] or "").split()) for b in beats)
    print(json.dumps(pl, indent=1))
    print(f"narration {words} words, about {words / 2.5:.0f}s at 150 wpm")
    if plan_only:
        return
    from tools.tool_registry import registry
    registry.discover()
    tts, vc = registry.get("tts_selector"), registry.get("video_compose")
    for d in ("assets", "artifacts", "renders"):
        (P / d).mkdir(exist_ok=True)
    pub = ROOT / f"remotion-composer/public/seo-{slug}"
    pub.mkdir(parents=True, exist_ok=True)

    GAP, TAIL = 0.35, 2.5

    def min_hold(card):
        """Every on-screen title stays at least 3s, plus 0.3s per word over 6 (Seth, 2026-10-28, #145)."""
        return CFG["title_hold_seconds"] + CFG["title_hold_per_extra_word"] * max(0, len(card.split()) - CFG["title_hold_free_words"])

    def silence(path, sec):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{sec:.2f}",
                        "-c:a", "libmp3lame", str(path)], check=True)
    sil = P / "assets/gap.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(GAP), "-c:a", "libmp3lame", str(sil)], check=True)
    spans, files, t = [], [], 0.0
    for key, card, say, cap, n, style in beats:
        if say:
            # a clip is kept per (voice, text), so a re-render for a layout change does not pay for the voice again
            out = P / f"assets/{slug}-{key}-{hashlib.sha1((CFG['voice_id'] + say).encode()).hexdigest()[:8]}.mp3"
            if not (out.exists() and out.stat().st_size > 0):
                r = tts.execute({"text": say, "preferred_provider": "elevenlabs", "voice_id": CFG["voice_id"],
                                 "model_id": CFG["tts_model"], "stability": 0.5, "similarity_boost": 0.85, "output_path": str(out)})
                assert r.success, f"{key}: {r.error}"
            d = dur(out)
            files.append(out)
            if d < min_hold(card):  # a short line keeps its card up: the voice, then silence to the minimum
                pad = P / f"assets/pad-{min_hold(card) - d:.2f}.mp3"
                silence(pad, min_hold(card) - d)
                files.append(pad)
                d = min_hold(card)
        else:
            out = P / f"assets/hold-{min_hold(card):.2f}.mp3"
            silence(out, min_hold(card))
            d = min_hold(card)
            files.append(out)
        spans.append((t, t + d + GAP))
        files.append(sil)
        t += d + GAP
    total = round(t + TAIL, 2)
    if not CFG["min_seconds"] <= total <= CFG["max_seconds"]:
        sys.exit(f"{slug}: {total}s is outside {CFG['min_seconds']}-{CFG['max_seconds']}s; trim beats or change max_sections")
    lst = P / f"assets/{slug}-list.txt"
    lst.write_text("".join(f"file '{f}'\n" for f in files))
    narr = pub / "narration.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-af", f"apad=whole_dur={total}",
                    "-c:a", "libmp3lame", "-q:a", "2", str(narr)], check=True)

    # Moving background: the site's own data-flow scene and scroll orb (#149, PR #150), recorded by bg/record_flow_bg.mjs.
    # The flow plays under every card; the orb assembles under the end card. The cards sit over it on a dark scrim.
    bg = pub / "bg.mp4"
    orb_at = spans[-1][0]
    build_background(P / "assets/bg", bg, total, orb_at)

    # The shared hero_title and callout components hard-code their own colours and sizes, so every card is a
    # text_card in the site's own colours.
    cuts, first_of = [], {}
    for (key, card, say, cap, n, (color, size)), (a, b) in zip(beats, spans):
        extra = {}
        img = pl["scenes"][n - 1]["image"] if n else None
        if img:
            ext = Path(urlparse(img).path).suffix or ".jpg"
            f = pub / f"s{n}{ext}"
            f.write_bytes(urllib.request.urlopen(img, timeout=30).read())
            extra["backgroundImage"] = f"seo-{slug}/{f.name}"  # the page's own image behind the section
        extra.update(backgroundVideo=f"seo-{slug}/bg.mp4", backgroundVideoStart=round(a, 2),
                     backgroundOverlay=0.25 if key == "outro" else 0.45, vignette=False)
        cuts.append({"id": key, "source": "", "backgroundColor": T["bg"], "in_seconds": round(a, 2),
                     "out_seconds": total if key == "outro" else round(b, 2), "transition_in": "fade", "transition_out": "fade",
                     "type": "text_card", "text": card.replace("  ·  ", "\n") if key == "outro" else card, "color": color,
                     "fontSize": size, "fadeOutSeconds": CFG["fade_seconds"],
                     **({"leftOffset": 0.05, "topOffset": 0.34} if key == "outro" else {"topOffset": 0.17}), **extra})
        first_of.setdefault(n if key != "outro" else "end", a)
    comp = {"version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data", "composition_mode": "templated",
            "cuts": cuts, "overlays": [], "captions": [],
            "audio": {"narration": {"src": f"seo-{slug}/narration.mp3", "volume": 1.0}},
            "themeConfig": {"primaryColor": T["accent"], "accentColor": T["accent"], "backgroundColor": T["bg"],
                            "surfaceColor": T["surface"], "textColor": T["text"], "mutedTextColor": T["muted"],
                            "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
                            "chartColors": [T["accent"], T["text"], T["muted"]],
                            "springConfig": {"damping": 22, "stiffness": 150, "mass": 1}, "transitionDuration": CFG["fade_seconds"]},
            "metadata": {"project_id": "seo-page-videos", "video": slug, "target_duration_seconds": total}}
    json.dump(comp, open(P / f"artifacts/{slug}-composition.json", "w"), indent=2)

    out = P / f"renders/{slug}.mp4"
    r = vc.execute({"operation": "render", "edit_decisions": comp, "asset_manifest": {"version": "1.0", "assets": []},
                    "script_text": " ".join(b[2] for b in beats if b[2]), "profile": "youtube_landscape",
                    "output_path": str(out), "remotion_timeout_ms": 600000})
    assert r.success, f"RENDER FAILED: {r.error}"

    # Captions go on YouTube as a sidecar track, never into the picture (Seth, 2026-10-08). The text is the script
    # itself, split into short cues over each beat's own time, so a name is never misheard into a caption.
    cues = []
    for (key, card, say, cap, n, _), (a, b) in zip(beats, spans):
        if not cap:
            continue
        ws = cap.split()
        chunks = [ws[i:i + 6] for i in range(0, len(ws), 6)]
        end = b - GAP
        for i, c in enumerate(chunks):
            cues.append((a + (end - a) * i / len(chunks), a + (end - a) * (i + 1) / len(chunks), " ".join(c)))
    out.with_suffix(".srt").write_text("".join(
        f"{i}\n{srt_time(int(x * 1000))} --> {srt_time(int(y * 1000))}\n{txt}\n\n" for i, (x, y, txt) in enumerate(cues, 1)))

    def mmss(sec):
        return f"{int(sec) // 60}:{int(sec) % 60:02d}"
    chapters = [("Intro", 0.0)] + [(sc["heading"], first_of[n]) for n, sc in enumerate(pl["scenes"], 1)] + [("Book a call", first_of["end"])]
    desc = (f"{pl['desc']}\n\nThe page: {url}\n\n" + "\n".join(f"{mmss(t)} {h}" for h, t in chapters)
            + f"\n\nSeth Shoultes, {CFG['site']}")
    json.dump({"title": f"{pl['title']} | Seth Shoultes", "description": desc, "url": url, "duration_seconds": total,
               "tags": ["Seth Shoultes", "Southern Utah", pl["title"]], "chapters": chapters,
               "voice": "Seth's own voice (ElevenLabs clone)"},
              open(out.with_suffix(".youtube.json"), "w"), indent=2)
    print("OK", f"{total}s", out)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 1:
        sys.exit(__doc__)
    main(a[0], "--plan-only" in sys.argv)
