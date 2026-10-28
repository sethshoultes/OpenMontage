"""Results video for the HTML-to-WordPress converter test (memberintel-marketing#720, piece 2 of #8803).

Usage: build_converter_video.py <wp-html-converter-test checkout> [--plan-only]
Env:   CARTESIA_SECRET_KEY (source ~/.config/dev-secrets/secrets.env)
Out:   projects/wpab-converter-test/renders/converter-test.mp4 (+ .srt sidecar, never burned in)

Scores only, no winner wording. Every number is read from results/SCORES.md (Totals table); the screenshots are the
repo's own results/<tool>/{original,converted}-index-1280.png. Order is the table's, not sorted by score.
Slides are drawn at 1920x1080, one per narration line, each held for its line (3s minimum) with a fade.
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
P = HERE.parent
CFG = json.load(open(HERE / "config.json"))
T = CFG["theme"]
W, H = 1920, 1080
FONT = "/System/Library/Fonts/Helvetica.ttc"
TOOLS = [  # SCORES.md name -> (results dir, who publishes it)
    ("rawhandler", "rawhandler", "built into WordPress"),
    ("Static Site Importer †", "static-site-importer", "from Automattic"),
    ("Blocks Engine", "blocks-engine", "from Automattic"),
    ("Block Runner", "block-runner", "from Human Made"),
    ("HTML to Blocks Converter", "html-to-blocks-converter", "from an independent developer"),
]


def font(size, bold=True):
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def scores(repo):
    rows = {}
    for line in (Path(repo) / "results/SCORES.md").read_text().split("## Per criterion")[0].splitlines():
        m = re.match(r"\| (.+?) \| (\d+) \| (\d+) \(72 less 2 per N/E cell\) \| (\d+) \|$", line) or re.match(r"\| (.+?) \| (\d+) \| (\d+) \| (\d+) \|$", line)
        if m and m.group(1) != "Tool":
            rows[m.group(1)] = tuple(int(x) for x in m.groups()[1:])
    assert len(rows) == 5, f"expected 5 tools in the Totals table, got {rows}"
    return rows


def canvas():
    im = Image.new("RGB", (W, H), T["bg"])
    return im, ImageDraw.Draw(im)


def centered(d, text, y, f, fill):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def wrap(d, text, f, width):
    out, line = [], ""
    for w in text.split():
        if d.textlength((line + " " + w).strip(), font=f) > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + [line]


def shot(repo, tool, kind, w):
    im = Image.open(Path(repo) / f"results/{tool}/{kind}-index-1280.png").convert("RGB")
    im = im.crop((0, 0, 1280, 1000))
    return im.resize((w, int(w * 1000 / 1280)), Image.LANCZOS)


def slide_title():
    im, d = canvas()
    centered(d, "Five HTML-to-WordPress converters", 380, font(96), T["accent"])
    centered(d, "One sample site, ten fixed checks", 520, font(64), T["text"])
    return im


def slide_sample(repo):
    im, d = canvas()
    s = shot(repo, "rawhandler", "original", 1300)
    im.paste(s, ((W - 1300) // 2, 200))
    centered(d, "The sample: Quillfern Cycle Works", 70, font(72), T["text"])
    centered(d, "a made-up bike shop, hand-coded HTML", 140, font(44, False), T["muted"])
    return im


def slide_tool(repo, name, tool, score, mx, ne):
    im, d = canvas()
    clean = name.replace(" †", "")
    d.text((90, 50), clean, font=font(84), fill=T["accent"])
    big = f"{score} of {mx}"
    wbig = d.textlength(big, font=font(84))
    d.text((W - 90 - wbig, 50), big, font=font(84), fill=T["text"])
    sub = f"{ne} checks had no evidence, left out of the maximum" if ne else "all ten checks had evidence"
    wsub = d.textlength(sub, font=font(36, False))
    d.text((W - 90 - wsub, 150), sub, font=font(36, False), fill=T["muted"])
    cw = 900
    for i, kind in enumerate(("original", "converted")):
        x = 60 + i * (cw + 0)
        im.paste(shot(repo, tool, kind, cw), (x, 250))
        d.text((x, 205), kind.capitalize(), font=font(40), fill=T["muted"])
    return im


def slide_table(rows):
    im, d = canvas()
    centered(d, "Totals, ten checks across four pages", 70, font(68), T["text"])
    x = [160, 960, 1300, 1620]
    for xi, h in zip(x, ("Tool", "Score", "Maximum", "No evidence")):
        d.text((xi, 220), h, font=font(40), fill=T["muted"])
    for i, (name, tool, _) in enumerate(TOOLS):
        y = 300 + i * 105
        sc, mx, ne = rows[name]
        d.rectangle((120, y - 14, W - 120, y + 78), fill=T["panel"])
        d.text((x[0], y), name.replace(" †", ""), font=font(52), fill=T["text"])
        d.text((x[1], y), str(sc), font=font(52), fill=T["accent"])
        d.text((x[2], y), str(mx), font=font(52), fill=T["text"])
        d.text((x[3], y), str(ne), font=font(52), fill=T["muted"])
    centered(d, "Plain sums of 0, 1 and 2 per check. No weights.", 880, font(44, False), T["muted"])
    return im


def slide_disclosures():
    im, d = canvas()
    d.text((120, 70), "Read these first", font=font(80), fill=T["accent"])
    items = ["One sample site, four pages.",
             "Four tools were given each page's body markup; Static Site Importer was given the whole site.",
             "Static Site Importer ran by its publisher's own Playground route, under a newer PHP.",
             "Run 2026-10-28, every tool pinned to a version."]
    y = 220
    for it in items:
        for j, ln in enumerate(wrap(d, it, font(52, False), W - 320)):
            d.text((120 + (0 if j == 0 else 50), y), ("•  " if j == 0 else "") + ln, font=font(52, False), fill=T["text"])
            y += 70
        y += 40
    return im


def slide_end():
    im, d = canvas()
    centered(d, "Scores and every screenshot are public", 330, font(72), T["text"])
    centered(d, CFG["repo"].replace("https://", ""), 450, font(52), T["accent"])
    centered(d, "The question comes from WordPress Agent Benchmarks", 640, font(52, False), T["text"])
    centered(d, CFG["benchmark"].replace("https://", ""), 720, font(44), T["accent"])
    return im


def script(rows):
    def n(name):
        s, m, ne = rows[name]
        return f"{s} out of {m}"
    lines = [("title", slide_title, "We ran five tools that turn an HTML page into WordPress blocks, on the same sample site, and scored each against ten fixed checks.")]
    lines.append(("sample", None, "The sample is Quillfern Cycle Works, a made-up bike shop."))
    leads = {"rawhandler": "First, rawHandler, built into WordPress", "Static Site Importer †": "Static Site Importer, from Automattic",
             "Blocks Engine": "Blocks Engine, also from Automattic", "Block Runner": "Block Runner, from Human Made",
             "HTML to Blocks Converter": "HTML to Blocks Converter, from an independent developer"}
    for name, tool, who in TOOLS:
        lines.append((tool, None, f"{leads[name]}: {n(name)}."))
    lines.append(("table", None, "Checks with no evidence are left out of each maximum. A lower score means fewer of the ten checks passed on this one sample site."))
    lines.append(("disclosures", None, "Please note: one sample site. Four tools got each page's body markup. Only Static Site Importer got the whole site, and it ran by its publisher's own route, on a newer PHP. Run on October 28th, 2026, every tool pinned to a version."))
    lines.append(("end", None, "The scores and every screenshot are public. The question comes from WordPress Agent Benchmarks."))
    return lines


def tts(text, out):
    body = {"model_id": CFG["tts_model"], "transcript": text, "voice": {"mode": "id", "id": CFG["voice_id"]}, "language": "en",
            "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
            "generation_config": {"speed": CFG["speed"]}}
    import os
    req = urllib.request.Request("https://api.cartesia.ai/tts/bytes", json.dumps(body).encode(), {
        "Authorization": f"Bearer {os.environ['CARTESIA_SECRET_KEY']}", "Cartesia-Version": "2025-04-16", "Content-Type": "application/json"})
    out.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    assert out.stat().st_size > 1000, out


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def srt_time(s):
    ms = int(s * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main(repo, plan_only):
    import hashlib
    rows = scores(repo)
    lines = script(rows)
    for k, _, t in lines:
        print(f"[{k}] {t}")
    print("words:", sum(len(t.split()) for _, _, t in lines))
    if plan_only:
        return
    for d in ("assets", "slides", "renders"):
        (P / d).mkdir(exist_ok=True)
    builders = {"title": slide_title, "sample": lambda: slide_sample(repo), "table": lambda: slide_table(rows),
                "disclosures": slide_disclosures, "end": slide_end}
    for name, tool, _ in TOOLS:
        builders[tool] = (lambda n=name, t=tool: slide_tool(repo, n, t, *rows[n]))
    GAP, TAIL, F = 0.4, 2.5, CFG["fade_seconds"]
    clips, t, cues = [], 0.0, []
    for key, _, text in lines:
        slide = P / f"slides/{key}.png"
        builders[key]().save(slide)
        a = P / f"assets/{key}-{hashlib.sha1((CFG['voice_id'] + str(CFG['speed']) + text).encode()).hexdigest()[:8]}.mp3"
        if not (a.exists() and a.stat().st_size > 0):
            tts(text, a)
        d = max(dur(a) + GAP, CFG["min_hold_seconds"])
        if key == "end":
            d += TAIL
        clip = P / f"assets/clip-{key}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", f"{d:.2f}", "-i", str(slide),
                        "-vf", f"fade=t=in:st=0:d={F},fade=t=out:st={d - F:.2f}:d={F},format=yuv420p",
                        "-c:v", "libx264", "-crf", "18", str(clip)], check=True)
        pad = P / f"assets/pad-{key}.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(a), "-af", f"apad=whole_dur={d:.2f}", "-t", f"{d:.2f}",
                        "-c:a", "libmp3lame", "-q:a", "2", str(pad)], check=True)
        clips.append((clip, pad))
        ws = text.split()
        chunks = [ws[i:i + 7] for i in range(0, len(ws), 7)]
        end = t + dur(a)
        for i, c in enumerate(chunks):
            cues.append((t + (end - t) * i / len(chunks), t + (end - t) * (i + 1) / len(chunks), " ".join(c)))
        t += d
    for ext, kind, f in (("v", "video", "clips-v.txt"), ("a", "audio", "clips-a.txt")):
        (P / f"assets/{f}").write_text("".join(f"file '{c[0 if ext == 'v' else 1]}'\n" for c in clips))
    out = P / "renders/converter-test.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(P / "assets/clips-v.txt"),
                    "-f", "concat", "-safe", "0", "-i", str(P / "assets/clips-a.txt"), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    out.with_suffix(".srt").write_text("".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{x}\n\n" for i, (a, b, x) in enumerate(cues, 1)))
    print("OK", f"{dur(out):.1f}s", out)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 1:
        sys.exit(__doc__)
    main(a[0], "--plan-only" in sys.argv)
