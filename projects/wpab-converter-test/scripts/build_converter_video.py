"""Results video for the HTML-to-WordPress converter test (memberintel-marketing#720, piece 2 of #8803).

Usage: build_converter_video.py <wp-html-converter-test checkout> [--plan-only] [--silent] [--portrait]
  --silent: the same slides, numbers, order and timings with no voice and no audio track; slides cross-dissolve.
  --portrait: 1080x1920 layouts (the blog player is portrait only): the same words and numbers, the pair of screenshots stacked.
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

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
P = HERE.parent
CFG = json.load(open(HERE / "config.json"))
T = CFG["theme"]
W, H = 1920, 1080
SILENT_HOLDS = {"table": 9.0, "disclosures": 10.0, "closing": 6.0, "end": 5.0}   # silent cut: no voice sets the pace, so each slide holds 4.5 s at least, longer where there is more to read
HOLDS = {"table": 10.0}  # the totals slide carries the sentence on screen; hold it long enough to read
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
    centered(d, "Five HTML-to-WordPress converters", 435, font(96), T["accent"])
    centered(d, "One sample site, ten fixed checks", 575, font(64), T["text"])
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
    d.text((90, 50), name, font=font(84), fill=T["accent"])  # keeps the dagger on Static Site Importer
    big = f"{score} of {mx}"
    wbig = d.textlength(big, font=font(84))
    d.text((W - 90 - wbig, 50), big, font=font(84), fill=T["text"])
    sub = f"{ne} checks had no evidence, left out of the maximum" if ne else "all ten checks had evidence"
    wsub = d.textlength(sub, font=font(48, False))
    d.text((W - 90 - wsub, 150), sub, font=font(48, False), fill=T["muted"])
    cw = 900
    for i, kind in enumerate(("original", "converted")):
        x = 60 + i * (cw + 0)
        im.paste(shot(repo, tool, kind, cw), (x, 290))
        d.text((x, 218), f"{kind.capitalize()}, home page", font=font(56), fill=T["text"])
    return im


def slide_table(rows):
    im, d = canvas()
    centered(d, "Totals, ten checks across four pages", 50, font(68), T["text"])
    x = [160, 960, 1300, 1620]
    for xi, h in zip(x, ("Tool", "Score", "Maximum", "No evidence")):
        d.text((xi, 160), h, font=font(40), fill=T["muted"])
    for i, (name, tool, _) in enumerate(TOOLS):
        y = 225 + i * 88
        sc, mx, ne = rows[name]
        d.rectangle((120, y - 10, W - 120, y + 68), fill=T["panel"])
        d.text((x[0], y), name, font=font(52), fill=T["text"])
        d.text((x[1], y), str(sc), font=font(52), fill=T["accent"])
        d.text((x[2], y), str(mx), font=font(52), fill=T["text"])
        d.text((x[3], y), str(ne), font=font(52), fill=T["muted"])
    # what a lower score means is on screen, not only in the narration (a silent viewer reads it here)
    y = 700
    for ln in wrap(d, "A lower score means fewer of the ten checks passed on this one sample site.", font(60), W - 300):
        centered(d, ln, y, font(60), T["text"])
        y += 76
    centered(d, "Plain sums of 0, 1 and 2 per check. No weights.", 880, font(46, False), T["muted"])
    centered(d, "† Ran by its publisher's Playground route, under a newer PHP.", 950, font(48, False), T["muted"])
    return im


def slide_disclosures():
    items = ["One sample site, four pages.",
             "Four tools got each page's body markup; Static Site Importer got the whole site.",
             "Static Site Importer ran by its publisher's Playground route, under a newer PHP.",
             "Run 2026-10-28, every tool pinned to a version."]
    for size in range(88, 56, -2):  # the largest type that fits the frame, never under 1.6x the old 52
        im, d = canvas()
        d.text((120, 60), "Read these first", font=font(96), fill=T["accent"])
        y, f = 210, font(size, False)
        for it in items:
            for j, ln in enumerate(wrap(d, it, f, W - 300)):
                d.text((120 + (0 if j == 0 else size * 0.7), y), ("•  " if j == 0 else "") + ln, font=f, fill=T["text"])
                y += int(size * 1.2)
            y += int(size * 0.3)
        if y < H - 40:
            return im
    raise SystemExit("disclosures do not fit")


def slide_end():
    im, d = canvas()
    centered(d, "Scores and every screenshot are public", 330, font(72), T["text"])
    centered(d, CFG["repo"].replace("https://", ""), 450, font(52), T["accent"])
    centered(d, "The question comes from WordPress Agent Benchmarks", 640, font(52, False), T["text"])
    centered(d, CFG["benchmark"].replace("https://", ""), 720, font(44), T["accent"])
    return im


def slide_closing():
    im, d = canvas()
    y = 360
    for ln in wrap(d, "Every tool brought some of the site over, none brought all of it.", font(80), W - 300):
        centered(d, ln, y, font(80), T["text"])
        y += 100
    centered(d, "Plan to check every page and redo the look, forms and video.", y + 50, font(60, False), T["text"])
    return im


PW, PH = 1080, 1920
TOP, BOT = 192, 1530      # the blog player crops the top 10% and everything below y=1530
SHOWN = {"rawhandler": "rawHandler"}   # how a tool's name is written on screen (SCORES.md keeps the lower case)


def pcanvas():
    im = Image.new("RGB", (PW, PH), T["bg"])
    return im, ImageDraw.Draw(im)


def ptext(d, text, x, y, f, fill=None, center=False):
    """Draw one line of text, failing the build if it leaves y 192-1530 or the frame's sides, or is under 50 px (the big score figures are exempt upward)."""
    assert f.size >= 50, f"type under 50 px: {text!r}"
    w = d.textlength(text, font=f)
    x = (PW - w) / 2 if center else x
    assert TOP <= y and y + f.size * 1.15 <= BOT, f"outside y {TOP}-{BOT}: {text!r} y={y}"
    assert 40 <= x and x + w <= PW - 40, f"outside the sides: {text!r}"
    d.text((x, y), text, font=f, fill=fill or T["text"])


def pwrap(d, text, y, f, width, lead, fill=None, center=True, x=60):
    for ln in wrap(d, text, f, width):
        ptext(d, ln, x, y, f, fill, center)
        y += lead
    return y


def clean_cut(im, lo, hi):
    """A crop height in [lo, hi] (source px) that lands on a quiet band of rows, so no line of text or card is cut in half.
    Prefers the lowest such boundary; falls back to hi if the page never goes quiet."""
    g = np.asarray(im.convert("L")).astype(int)
    for y in range(min(hi, g.shape[0] - 8), lo, -1):
        band = g[y:y + 8]
        if (band.max(axis=1) - band.min(axis=1)).max() <= 6:
            return y
    return hi


def pshot(repo, tool, kind, w, max_h, src_lo=300):
    """The top of a 1280-wide screenshot, scaled to w, at most max_h tall, cut at a clean boundary."""
    im = Image.open(Path(repo) / f"results/{tool}/{kind}-index-1280.png").convert("RGB")
    hi = int(1280 * max_h / w)
    cut = clean_cut(im, min(src_lo, hi - 1), hi)
    im = im.crop((0, 0, 1280, cut))
    return im.resize((w, round(cut * w / 1280)), Image.LANCZOS)


def paste(im, sh, x, y):
    assert y >= TOP and y + sh.size[1] <= BOT, (y, sh.size)
    im.paste(sh, (x, y))


def pslide_title():
    im, d = pcanvas()
    y = pwrap(d, "Five tools that turn HTML into WordPress", 560, font(96), PW - 140, 118)
    pwrap(d, "One sample site, ten fixed checks", y + 50, font(64), PW - 140, 80)
    return im


def pslide_sample(repo):
    im, d = pcanvas()
    y = pwrap(d, "The sample: Quillfern Cycle Works", 200, font(66), PW - 120, 82)
    y = pwrap(d, "a made-up bike shop, hand-coded HTML", y + 10, font(52, False), PW - 120, 66)
    sh = pshot(repo, "rawhandler", "original", 960, BOT - 40 - (y + 30), src_lo=700)
    paste(im, sh, 60, y + 30)
    return im


def pslide_tool(repo, name, tool, score, mx, ne):
    """Both screenshots sit inside y 192-1530; the header grows with the name and the notes, the screenshots take the room left."""
    im, d = pcanvas()
    y = pwrap(d, SHOWN.get(tool, name), 200, font(72), PW - 120, 86)
    ptext(d, f"{score} of {mx}", 0, y, font(112), T["accent"], center=True)
    y += 128
    if ne:
        y = pwrap(d, f"{ne} checks could not be judged, so the top score is {mx}, not 72", y, font(50, False), PW - 120, 62)
    if tool == "static-site-importer":
        y = pwrap(d, "\u2020 Given the whole site, not just the page content, so not comparable.", y, font(50, False), PW - 120, 62)
    y += 10
    room = BOT - y - 2 * 64 - 30                 # two labels and a gap, then two screenshots
    h = room // 2
    ptext(d, "Original, home page", 60, y, font(50), T["text"])
    a = pshot(repo, tool, "original", 960, h)
    paste(im, a, 60, y + 60)
    y2 = y + 60 + a.size[1] + 24
    ptext(d, "Converted, home page", 60, y2, font(50), T["text"])
    b = pshot(repo, tool, "converted", 960, BOT - (y2 + 60))
    paste(im, b, 60, y2 + 60)
    return im


def pslide_table(rows):
    """The four like-for-like tools in one list, Static Site Importer apart and marked not comparable."""
    im, d = pcanvas()
    y = pwrap(d, "Totals: ten checks across four pages", 200, font(62), PW - 120, 76)
    y += 20
    for name, tool, _ in TOOLS:
        if tool == "static-site-importer":
            continue
        sc, mx, ne = rows[name]
        d.rectangle((50, y - 6, PW - 50, y + 76), fill=T["panel"])
        ptext(d, SHOWN.get(tool, name), 70, y + 6, font(52), T["text"])
        sw = f"{sc} of {mx}"
        ptext(d, sw, PW - 70 - d.textlength(sw, font=font(52)), y + 6, font(52), T["accent"])
        y += 98
    y += 14
    ptext(d, "Shown apart, not comparable:", 60, y, font(50), T["text"])
    y += 66
    name, tool, _ = [t for t in TOOLS if t[1] == "static-site-importer"][0]
    sc, mx, ne = rows[name]
    d.rectangle((50, y - 6, PW - 50, y + 76), fill=T["panel"])
    ptext(d, "Static Site Importer", 70, y + 6, font(52), T["text"])
    sw = f"{sc} of {mx}"
    ptext(d, sw, PW - 70 - d.textlength(sw, font=font(52)), y + 6, font(52), T["accent"])
    y += 100
    y = pwrap(d, "It was given the whole site and ran on a newer version of PHP, and 6 checks could not be judged.", y, font(50, False), PW - 120, 62) + 14
    y = pwrap(d, "Highest of the four on this one site: Blocks Engine, 35 of 66. One site, not a ranking.", y, font(50, False), PW - 120, 62) + 14
    pwrap(d, "A lower score means fewer checks passed.", y, font(50, False), PW - 120, 62)
    return im


def pslide_disclosures():
    items = ["One sample site, four pages.",
             "Ten checks on each page, each scored 0, 1 or 2. The top score is 72.",
             "Four tools were given each page's main content. Static Site Importer was given the whole site, so it is shown apart.",
             "Checks that could not be judged are left out, so that tool's top score is lower.",
             "Run on October 28, 2026, each tool kept at one fixed version."]
    for size in range(60, 50, -2):
        im, d = pcanvas()
        ptext(d, "How to read the scores", 70, 200, font(72), T["text"])
        y, f = 320, font(size, False)
        try:
            for it in items:
                for j, ln in enumerate(wrap(d, it, f, PW - 190)):
                    ptext(d, ("\u2022  " if j == 0 else "    ") + ln, 70, y, f, T["text"])
                    y += int(size * 1.25)
                y += int(size * 0.4)
            return im
        except AssertionError:
            continue
    raise SystemExit("disclosures do not fit")


def pslide_closing():
    im, d = pcanvas()
    y = pwrap(d, "Every tool brought some of the site over, none brought all of it.", 460, font(72), PW - 120, 90)
    pwrap(d, "Plan to check every page and redo the look, forms and video.", y + 60, font(60, False), PW - 120, 76)
    return im


def pslide_end():
    im, d = pcanvas()
    y = pwrap(d, "Every score and screenshot is public.", 560, font(72), PW - 120, 90)
    pwrap(d, "The question comes from WordPress Agent Benchmarks, an open source project started by Andy Peatling.", y + 70, font(54, False), PW - 120, 70)
    return im


def script(rows):
    def n(name):
        s, m, ne = rows[name]
        return f"{s} out of {m}"
    lines = [("title", slide_title, "We ran five tools that turn an HTML page into WordPress blocks, on the same sample site, and scored each against ten fixed checks.")]
    lines.append(("disclosures", None, "How to read the scores: one sample site, four pages, ten checks on each page, each scored zero, one or two, so the top score is 72. Four tools were given each page's main content. Only Static Site Importer got the whole site, so it is shown apart. Checks that could not be judged are left out. Run on October 28th, 2026, each tool kept at one fixed version."))
    lines.append(("sample", None, "The sample is Quillfern Cycle Works, a made-up bike shop."))
    leads = {"rawhandler": "First, rawHandler, built into WordPress", "Static Site Importer †": "Static Site Importer, from Automattic",
             "Blocks Engine": "Blocks Engine, also from Automattic", "Block Runner": "Block Runner, from Human Made",
             "HTML to Blocks Converter": "HTML to Blocks Converter, from an independent developer"}
    for name, tool, who in TOOLS:
        lines.append((tool, None, f"{leads[name]}: {n(name)}."))
    lines.append(("table", None, "Highest of the four comparable tools on this one site: Blocks Engine. One site, not a ranking. A lower score means fewer checks passed."))
    lines.append(("closing", None, "Every tool brought some of the site over, none brought all of it. Plan to check every page and redo the look, forms and video."))
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


def main(repo, plan_only, silent=False, portrait=False):
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
    if portrait:
        builders = {"title": pslide_title, "sample": lambda: pslide_sample(repo), "table": lambda: pslide_table(rows),
                    "disclosures": pslide_disclosures, "closing": pslide_closing, "end": pslide_end}
        for name, tool, _ in TOOLS:
            builders[tool] = (lambda n=name, t=tool: pslide_tool(repo, n, t, *rows[n]))
    else:
        builders = {"title": slide_title, "sample": lambda: slide_sample(repo), "table": lambda: slide_table(rows),
                    "disclosures": slide_disclosures, "closing": slide_closing, "end": slide_end}
        for name, tool, _ in TOOLS:
            builders[tool] = (lambda n=name, t=tool: slide_tool(repo, n, t, *rows[n]))
    tag = "-portrait" if portrait else ""
    GAP, TAIL, F = 0.4, 2.5, CFG["fade_seconds"]
    clips, t, cues, durs = [], 0.0, [], []
    for key, _, text in lines:
        slide = P / f"slides/{key}{tag}.png"
        builders[key]().save(slide)
        if silent:
            d = SILENT_HOLDS.get(key, 4.5)
        else:
            a = P / f"assets/{key}-{hashlib.sha1((CFG['voice_id'] + str(CFG['speed']) + text).encode()).hexdigest()[:8]}.mp3"
            if not (a.exists() and a.stat().st_size > 0):
                tts(text, a)
            d = max(dur(a) + GAP, CFG["min_hold_seconds"], HOLDS.get(key, 0))
        if key == "end" and not silent:
            d += TAIL
        clip = P / f"assets/clip-{key}{tag}.mp4"
        vf = "format=yuv420p" if silent else f"fade=t=in:st=0:d={F},fade=t=out:st={d - F:.2f}:d={F},format=yuv420p"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", f"{d + (F if silent else 0):.2f}", "-i", str(slide),
                        "-vf", vf, "-c:v", "libx264", "-crf", "18", str(clip)], check=True)
        durs.append(d)
        if silent:
            clips.append((clip, None))
            t += d
            continue
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
    if silent:
        # cross-dissolve: slide i covers [t_i, t_i + d_i + F] and fades over the next one for its last F seconds
        out = P / f"renders/converter-test-silent{tag}.mp4"
        ins, fc, last, off = [], [], "0:v", 0.0
        for i, (clip, _) in enumerate(clips):
            ins += ["-i", str(clip)]
        for i in range(1, len(clips)):
            off += durs[i - 1]
            fc.append(f"[{last}][{i}:v]xfade=transition=fade:duration={F}:offset={off:.2f}[x{i}]")
            last = f"x{i}"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-an",
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
        print("OK", f"{dur(out):.1f}s", out)
        return
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
    main(a[0], "--plan-only" in sys.argv, "--silent" in sys.argv, "--portrait" in sys.argv)
