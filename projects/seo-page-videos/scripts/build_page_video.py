"""One sethshoultes.com page URL in, one 45-90 second SEO video out (sethshoultes.github.io#145).

Usage: build_page_video.py <page-url> [--plan-only]
Env:   ELEVENLABS_API_KEY (source ~/.config/dev-secrets/secrets.env)
Out:   projects/seo-page-videos/renders/<slug>.mp4, <slug>.srt (YouTube caption track, never burned in),
       <slug>.youtube.json (title, description with the page link, tags, chapters)

Scenes: title card, one card per page section (its key points as on-screen text, the page's own image
behind it when the section has one), end card with the site and the call to action. The voiceover reads the
page's own summary and first sentences in Seth's ElevenLabs voice (config.json, the one place the voice id
lives). --plan-only prints the script and scenes without spending anything.
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
    ov = Path(__file__).parent / "pages" / f"{slug}.json"  # optional hand-written on-screen points, by section heading
    override = json.load(open(ov))["points"] if ov.exists() else {}
    scenes = []
    for s in body:
        s["paras"] = [p for p in s["paras"] if len(p.split()) > 2]
        points = override.get(s["heading"]) or [short(i) for i in s["items"] if len(i.split()) > 1][:4] or [short(p) for p in s["paras"]][:3]
        scenes.append({"heading": s["heading"], "points": points,
                       "say": " ".join(sentences(s["paras"][0])[:2]),
                       "image": urljoin(url, s["images"][0]) if s["images"] else None})
    return {"url": url, "title": title, "intro": intro, "desc": pg.desc, "scenes": scenes,
            "outro": f"Want to talk it through? Book a call at {CFG['site'].replace('.', ' dot ')}."}


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def srt_time(ms):
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main(url, plan_only):
    pl = plan(url)
    slug = urlparse(url).path.strip("/").replace("/", "-") or "home"
    parts = [("intro", pl["intro"])] + [(f"s{n}", s["say"]) for n, s in enumerate(pl["scenes"], 1)] + [("outro", pl["outro"])]
    words = sum(len(t.split()) for _, t in parts) + len(pl["title"].split())
    print(json.dumps(pl, indent=1))
    print(f"narration {words} words, about {words / 2.5:.0f}s at 150 wpm")
    if plan_only:
        return
    from tools.tool_registry import registry
    registry.discover()
    tts, vc = registry.get("tts_selector"), registry.get("video_compose")
    (P / "assets").mkdir(exist_ok=True)
    (P / "artifacts").mkdir(exist_ok=True)
    (P / "renders").mkdir(exist_ok=True)
    pub = ROOT / f"remotion-composer/public/seo-{slug}"
    pub.mkdir(parents=True, exist_ok=True)

    clips = {}
    title_say = pl["title"] + "."
    for key, text in [("title", title_say)] + parts:
        # a clip is kept per (voice, text), so a re-render for a layout change does not pay for the voice again
        out = P / f"assets/{slug}-{key}-{hashlib.sha1((CFG['voice_id'] + text).encode()).hexdigest()[:8]}.mp3"
        if out.exists() and out.stat().st_size > 0:
            clips[key] = out
            continue
        r = tts.execute({"text": text, "preferred_provider": "elevenlabs", "voice_id": CFG["voice_id"],
                         "model_id": CFG["tts_model"], "stability": 0.5, "similarity_boost": 0.85, "output_path": str(out)})
        assert r.success, f"{key}: {r.error}"
        clips[key] = out
    order = ["title", "intro"] + [k for k, _ in parts[1:-1]] + ["outro"]
    GAP, TAIL = 0.35, 3.0
    # one narration track, a short breath between parts; the cut times come from the clip lengths, so nothing drifts
    cuts_at, t = {}, 0.0
    for k in order:
        d = dur(clips[k])
        cuts_at[k] = (round(t, 2), round(t + d + GAP, 2))
        t += d + GAP
    total = round(t + TAIL, 2)
    if not CFG["min_seconds"] <= total <= CFG["max_seconds"]:
        sys.exit(f"{slug}: {total}s is outside {CFG['min_seconds']}-{CFG['max_seconds']}s; change max_sections or the page copy")
    lst = P / f"assets/{slug}-list.txt"
    sil = P / "assets/gap.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(GAP), "-c:a", "libmp3lame", str(sil)], check=True)
    lst.write_text("".join(f"file '{clips[k]}'\nfile '{sil}'\n" for k in order))
    narr = pub / "narration.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-af", f"apad=whole_dur={total}",
                    "-c:a", "libmp3lame", "-q:a", "2", str(narr)], check=True)

    def span(key):
        a, b = cuts_at[key]
        return a, (total if key == order[-1] else b)

    def cut(cid, a, b, **kw):
        return {"id": cid, "source": "", "backgroundColor": T["bg"], "in_seconds": round(a, 2), "out_seconds": round(b, 2),
                "transition_in": "fade", "transition_out": "fade", **kw}

    # The shared hero_title and callout components hard-code their own colours and sizes, so every scene is a
    # text_card in the site's own colours: the title, then each section as its heading and points, one at a time.
    cuts = [cut("c0", 0, cuts_at["intro"][1], type="text_card", text=pl["title"], color=T["accent"], fontSize=150)]
    for n, s in enumerate(pl["scenes"], 1):
        a, b = span(f"s{n}")
        extra = {}
        if s["image"]:
            ext = Path(urlparse(s["image"]).path).suffix or ".jpg"
            img = pub / f"s{n}{ext}"
            img.write_bytes(urllib.request.urlopen(s["image"], timeout=30).read())
            extra["backgroundImage"] = f"seo-{slug}/{img.name}"  # the page's own image behind the section
        items = [(s["heading"], T["accent"], 100)] + [(p, T["text"], 100) for p in s["points"]]
        step = (b - a) / len(items)
        for i, (text, color, size) in enumerate(items):
            cuts.append(cut(f"c{n}-{i}", a + i * step, a + (i + 1) * step if i < len(items) - 1 else b,
                            type="text_card", text=text, color=color, fontSize=size, **extra))
    a, b = span("outro")
    cuts.append(cut("cend", a, b, type="text_card", text=f"{CFG['site']}  ·  {CFG['cta']}", color=T["accent"], fontSize=110))
    comp = {"version": "1.0", "render_runtime": "remotion", "renderer_family": "explainer-data", "composition_mode": "templated",
            "cuts": cuts, "overlays": [], "captions": [],
            "audio": {"narration": {"src": f"seo-{slug}/narration.mp3", "volume": 1.0}},
            "themeConfig": {"primaryColor": T["accent"], "accentColor": T["accent"], "backgroundColor": T["bg"],
                            "surfaceColor": T["surface"], "textColor": T["text"], "mutedTextColor": T["muted"],
                            "headingFont": "Inter", "bodyFont": "Inter", "monoFont": "JetBrains Mono",
                            "chartColors": [T["accent"], T["text"], T["muted"]],
                            "springConfig": {"damping": 22, "stiffness": 150, "mass": 1}, "transitionDuration": 0.35},
            "metadata": {"project_id": "seo-page-videos", "video": slug, "target_duration_seconds": total}}
    json.dump(comp, open(P / f"artifacts/{slug}-composition.json", "w"), indent=2)

    out = P / f"renders/{slug}.mp4"
    r = vc.execute({"operation": "render", "edit_decisions": comp, "asset_manifest": {"version": "1.0", "assets": []},
                    "script_text": " ".join(t for _, t in parts), "profile": "youtube_landscape",
                    "output_path": str(out), "remotion_timeout_ms": 600000})
    assert r.success, f"RENDER FAILED: {r.error}"

    # captions go on YouTube as a sidecar track, never into the picture (Seth, 2026-10-08)
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel("base", device="cpu", compute_type="int8").transcribe(str(narr), word_timestamps=True, language="en")
    cues, cue = [], []
    for sg in segs:
        for w in sg.words or []:
            wd = {"word": w.word.strip(), "s": int(w.start * 1000), "e": int(w.end * 1000)}
            if cue and (len(cue) >= 6 or wd["e"] - cue[0]["s"] > 2500):
                cues.append(cue)
                cue = []
            cue.append(wd)
    if cue:
        cues.append(cue)
    out.with_suffix(".srt").write_text("".join(
        f"{i}\n{srt_time(c[0]['s'])} --> {srt_time(c[-1]['e'])}\n{' '.join(w['word'] for w in c)}\n\n" for i, c in enumerate(cues, 1)))

    def mmss(sec):
        return f"{int(sec) // 60}:{int(sec) % 60:02d}"
    chapters = [("Intro", 0.0)] + [(s["heading"], cuts_at[f"s{n}"][0]) for n, s in enumerate(pl["scenes"], 1)] + [("Book a call", cuts_at["outro"][0])]
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
