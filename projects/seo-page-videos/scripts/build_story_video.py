"""Designed motion explainer from a story file: one concept still per narration beat, camera moves, real transitions,
kinetic type timed to the voice, a music bed ducked under the voice (v3 of the page video, sethshoultes.github.io#145).

Usage: build_story_video.py <story.json> <stills-dir> <vo-dir> <out.mp4> --music bed.mp3 --sfx a.mp3,b.mp3
  story.json   beats[]: id, vo, to_next (transition), kinetic [[text, anchor word]], shots[] {still, at (anchor word), cam, notype} (see stories/)
  stills-dir   <id>.png per shot, 16:9, 2k or larger (made on Higgsfield / Nano Banana Pro; see the story's image prompts)
  vo-dir       picked.json + <id>-tN.mp3/.json from gen_vo.py (the takes' character timings drive the type)
Everything visual is drawn per frame here (crop, transition, type), so edges stay pin-sharp: no upscaler, no blur, no glow.
No overlay of any kind is blended over the art (no haze, no glow): transitions are hard-edged pushes, wipes and circle reveals.
Captions are written as a sidecar .srt, never burned in.
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import story_mix

HERE = Path(__file__).parent
CFG = json.load(open(HERE / "config.json"))
W, H, FPS = 1920, 1080, 30
BEAT_T, INTRA_T = 0.5, 0.3   # transition length between beats, and between the sub-shots of one beat (s)
INTRA = ["slide-left", "wipe-right", "circle-open", "push-right", "wipe-up"]
GAP = 0.18                    # breath after each line
LEAD = 0.35
TAIL = 1.4
HOLD_MIN = 1.5                # a kinetic title stays at least 1.5 s
ART_W, ART_H = 1680, 950      # the still is shown in the top 950 px; the bottom 130 px is the type band, so type never covers art
ART_X = (W - ART_W) // 2
ORANGE = (255, 107, 44)
FONT = "/System/Library/Fonts/Helvetica.ttc"
ease = lambda x: 0.5 - 0.5 * math.cos(math.pi * min(1, max(0, x)))


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def word_times(align):
    """[(word, start_s)] from ElevenLabs character timings."""
    chars, starts = align["characters"], align["character_start_times_seconds"]
    out, cur, t0 = [], "", None
    for c, s in zip(chars, starts):
        if c.isspace():
            if cur:
                out.append((re.sub(r"[^a-z0-9.'-]", "", cur.lower()), t0))
            cur, t0 = "", None
        else:
            if not cur:
                t0 = s
            cur += c
    if cur:
        out.append((re.sub(r"[^a-z0-9.'-]", "", cur.lower()), t0))
    return out


def camera(shot, u, n):
    """(zoom, cx, cy) at normalised time u of shot n: waypoints if the story gives them, else a slow push that alternates sides."""
    pts = shot.get("cam")
    if not pts:
        side = (-1) ** n
        pts = [[0, 1.0, 0.5 - 0.02 * side, 0.5], [1, 1.07, 0.5 + 0.02 * side, 0.495]]
    for a, b in zip(pts, pts[1:]):
        if u <= b[0]:
            k = ease((u - a[0]) / max(1e-6, b[0] - a[0]))
            return tuple(a[i] + (b[i] - a[i]) * k for i in (1, 2, 3))
    return tuple(pts[-1][1:])


def ground_of(img):
    """The still's own ground colour (its border), so the frame around the art has no visible edge."""
    px = [img.getpixel((x, y)) for x in (3, 40, 80) for y in (3, 40, 80, img.size[1] - 4)]
    return tuple(int(sum(c[i] for c in px) / len(px)) for i in range(3))


def view(img, z, cx, cy):
    w, h = img.size
    cw, ch = w / z, h / z
    x0 = min(max(cx * w - cw / 2, 0), w - cw)
    y0 = min(max(cy * h - ch / 2, 0), h - ch)
    art = img.transform((ART_W, ART_H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
    canvas = Image.new("RGB", (W, H), ground_of(img))
    canvas.paste(art, (ART_X, 0))
    return canvas


def blend(a, b, kind, k):
    """Frame a -> frame b at progress k (0..1), as float arrays."""
    k = ease(k)
    if kind in ("push-left", "push-right", "slide-left"):
        dx = int(W * k) * (1 if kind == "push-right" else -1)
        out = np.empty_like(a)
        if dx < 0:
            out[:, :W + dx] = a[:, -dx:] if kind == "push-left" else a[:, :W + dx]
            out[:, W + dx:] = b[:, :-dx]
        else:
            out[:, dx:] = a[:, :W - dx]
            out[:, :dx] = b[:, W - dx:]
        return out
    if kind in ("wipe-up", "wipe-right"):
        out = a.copy()
        if kind == "wipe-up":
            r = int(H * (1 - k))
            out[r:] = b[r:]
            out[max(r - 6, 0):r] = ORANGE
        else:
            c = int(W * k)
            out[:, :c] = b[:, :c]
            out[:, c:c + 6] = ORANGE
        return out
    if kind in ("circle-open", "orb-burst"):
        yy, xx = np.ogrid[:H, :W]
        rad = k * math.hypot(W, H) / 2
        d = np.hypot(xx - W / 2, yy - H / 2)
        out = np.where((d < rad)[..., None], b, a)
        ring = (np.abs(d - rad) < 7)[..., None]
        return np.where(ring, np.array(ORANGE, dtype=a.dtype), out)
    if kind == "zoom-through":
        s = 1 + 0.6 * k
        ya = np.clip(((np.arange(H) - H / 2) / s + H / 2).astype(int), 0, H - 1)
        xa = np.clip(((np.arange(W) - W / 2) / s + W / 2).astype(int), 0, W - 1)
        za = a[ya][:, xa]
        return za * (1 - k) + b * k
    return a * (1 - k) + b * k


def type_overlay(phrases, t, font, beat_end):
    """RGBA kinetic title for time t. Each phrase pops in word by word and holds until the next phrase arrives (the band is never
    empty while he is speaking); the last one holds to the end of the line. A title is on screen at least HOLD_MIN seconds."""
    act = None
    for i, (text, t0) in enumerate(phrases):
        end = phrases[i + 1][1] if i + 1 < len(phrases) else beat_end + 0.3
        end = max(end, t0 + HOLD_MIN) if i + 1 == len(phrases) else end
        if t0 <= t < end + 0.12:
            act = (text, t0, end)
    if not act:
        return None
    text, t0, end = act
    words = text.split()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    widths = [d.textlength(w + " ", font=font) for w in words]
    x0, y0 = ART_X + 28, ART_H - 33   # the band sits clear of title-safe on a phone or player
    fade = 1.0 if t < end else max(0, 1 - (t - end) / 0.12)
    rise = 0 if t < end else int(24 * (t - end) / 0.12)
    d.rectangle((ART_X - 6, y0 + 10, ART_X + 4, y0 + 96), fill=ORANGE + (int(255 * fade),))
    x = x0
    for idx, (w, wd) in enumerate(zip(words, widths)):
        k = ease((t - t0 - 0.05 * idx) / 0.10)
        if k > 0:
            yoff = int((1 - k) * 30) - rise
            d.text((x, y0 + yoff), w, font=font, fill=(255, 255, 255, int(255 * fade)))
        x += wd
    return layer


ORANGE_PX = lambda a: (np.abs(a[..., 0].astype(int) - 255) < 45) & (np.abs(a[..., 1].astype(int) - 107) < 55) & (np.abs(a[..., 2].astype(int) - 44) < 60)


def apply_fx(img, fx, t):
    """Animate inside a still without any new asset: 'rows' (ten link rows slide away, three stay and light up),
    'draw' (the orange line of a chart draws left to right), 'pulse' (a hard ring at the line's end)."""
    a = np.asarray(img).copy()
    h, w, _ = a.shape
    ground = a[4, 4].copy()
    if fx["type"] == "rows":
        light = (a.min(axis=2) > 150)
        ys, xs = np.where(light)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        n = 10
        bh = (y1 - y0 + 1) / n
        out = a.copy()
        out[y0:y1 + 1, x0:x1 + 1] = ground
        for k in range(n):
            ya, yb = int(y0 + k * bh), int(y0 + (k + 1) * bh)
            band = a[ya:yb, x0:x1 + 1].copy()
            if k >= n - 3:   # the three that stay light up
                m = band.min(axis=2) > 150
                band[m] = ORANGE
                out[ya:yb, x0:x1 + 1] = band
            else:
                e = ease((t - fx["at"] - k * 0.07) / 0.55)
                dx = int(e * (w * 0.7)) * (1 if k % 2 else -1)
                xa = x0 + dx
                lo, hi = max(xa, 0), min(xa + band.shape[1], w)
                if hi > lo:
                    out[ya:yb, lo:hi] = band[:, lo - xa:hi - xa]
        return Image.fromarray(out)
    if fx["type"] in ("draw", "pulse"):
        m = ORANGE_PX(a)
        ys, xs = np.where(m)
        if len(xs) == 0:
            return img
        xmin, xmax = xs.min(), xs.max()
        if fx["type"] == "draw":
            prog = ease((t - fx["at"]) / fx.get("dur", 1.3))
            cut = xmin + (xmax - xmin) * prog
            hide = m.copy()
            hide[:, :int(cut)] = False
            # only the chart line: keep the title bar and tag (orange-free here anyway)
            a[hide] = ground
            return Image.fromarray(a)
        # pulse: hard ring at the line's right end, twice
        tip = xs >= xmax - 25
        cx, cy = int(xs[tip].mean()), int(ys[tip].mean())
        im = Image.fromarray(a)
        d = ImageDraw.Draw(im)
        for k in range(2):
            u = (t - fx["at"] - k * 0.55) / 0.5
            if 0 <= u <= 1:
                r = int(50 + 260 * ease(u))
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ORANGE, width=max(4, int(26 * (1 - u))))
        return im
    return img


def chip(frame_img, kind, k):
    """The through-line object: an orange quote chip that rides every beat change, then is gone."""
    d = ImageDraw.Draw(frame_img)
    size = 270
    if kind in ("push-left", "slide-left"):
        cx, cy, sc = W * (1 - k) - 0, H * 0.45, 1.0
    elif kind in ("push-right", "wipe-right"):
        cx, cy, sc = W * k, H * 0.45, 1.0
    elif kind == "wipe-up":
        cx, cy, sc = W / 2, H * (1 - k), 1.0
    else:   # circle-open, orb-burst, zoom-through: it punches out from the centre
        cx, cy, sc = W / 2, H * 0.45, math.sin(math.pi * k) * 1.5
    if sc <= 0.05:
        return frame_img
    s = int(size * sc)
    box = (cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2)
    d.rounded_rectangle((box[0] + 12, box[1] + 12, box[2] + 12, box[3] + 12), s // 6, fill=(60, 30, 14))
    d.rounded_rectangle(box, s // 6, fill=ORANGE)
    d.text((cx, cy + s * 0.12), "\u201c", font=ImageFont.truetype(FONT, int(s * 1.1), index=1), fill=(255, 255, 255), anchor="mm")
    return frame_img


def endcard(t, site, label):
    """The closing card, animated: a rule draws, the address slides up, the button pops with a little overshoot and presses."""
    ground = (23, 17, 12)
    im = Image.new("RGB", (W, H), ground)
    d = ImageDraw.Draw(im)
    cream = (241, 230, 214)
    back = lambda x: 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2   # ease-out-back
    rw = int(150 * ease(t / 0.4))
    d.rectangle((W / 2 - rw, 372, W / 2 + rw, 380), fill=ORANGE)
    k = ease((t - 0.15) / 0.45)
    if k > 0:
        d.text((W / 2, 480 + int((1 - k) * 46)), site, font=ImageFont.truetype(FONT, 168, index=1), fill=cream, anchor="mm")
    kb = min(1.0, max(0.0, (t - 0.9) / 0.35))
    if kb > 0:
        sc = back(kb) * (0.94 if 1.9 < t < 2.05 else 1.0)
        bw, bh = int(700 * sc), int(170 * sc)
        cx, cy = W / 2, 690
        d.rounded_rectangle((cx - bw / 2 + 12, cy - bh / 2 + 12, cx + bw / 2 + 12, cy + bh / 2 + 12), bh // 2, fill=(70, 38, 20))
        d.rounded_rectangle((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), bh // 2, fill=ORANGE)
        d.text((cx, cy), label, font=ImageFont.truetype(FONT, int(84 * sc), index=1), fill=ground, anchor="mm")
    return im


def main(story_path, stills, vo_dir, out, music, sfx_files):
    story = json.load(open(story_path))
    picked = json.load(open(Path(vo_dir) / "picked.json"))
    beats = story["beats"]
    font = ImageFont.truetype(FONT, 96, index=1)
    # beat timeline: each line starts after the last one plus a breath
    t = LEAD
    for bt in beats:
        pk = picked["s" + bt["id"][1:]]
        mp3 = Path(vo_dir) / pk["file"]
        al = json.load(open(str(mp3)[:-4] + ".json"))
        bt["mp3"], bt["d"], bt["words"], bt["start"] = mp3, dur(mp3), word_times(al), t
        t += bt["d"] + GAP
    total = round(t + TAIL, 2)
    # flat shot list; a sub-shot starts at its anchor word (a hair early, so the picture leads the voice)
    shots, bi = [], 0
    for bn, bt in enumerate(beats):
        j = 0
        for k, sh in enumerate(bt["shots"]):
            at = bt["start"]
            if sh.get("at"):
                m = next((i for i in range(j, len(bt["words"])) if bt["words"][i][0].startswith(sh["at"].lower())), None)
                if m is None:
                    sys.exit(f"{bt['id']}: anchor {sh['at']!r} not found in {[w for w, _ in bt['words']]}")
                at = bt["start"] + bt["words"][m][1] - 0.12
                j = m + 1
            shots.append({"beat": bn, "still": sh["still"], "at": at, "cam": sh.get("cam"), "notype": sh.get("notype", False), "fx": sh.get("fx", []),
                          "tr": bt["to_next"] if k == len(bt["shots"]) - 1 else sh.get("tr", INTRA[(len(shots)) % len(INTRA)])})
        # kinetic phrases for the beat, absolute time, anchored on the spoken word (searched in order)
        ph, j = [], 0
        for text, anchor in bt["kinetic"]:
            m = next((i for i in range(j, len(bt["words"])) if bt["words"][i][0].startswith(anchor.lower())), None)
            if m is None:
                sys.exit(f"{bt['id']}: kinetic anchor {anchor!r} not found")
            ph.append((text, bt["start"] if not ph else bt["start"] + bt["words"][m][1]))
            j = m + 1
        bt["phrases"] = ph
    n = len(shots)
    for i, sh in enumerate(shots):
        sh["end"] = shots[i + 1]["at"] if i + 1 < n else total
        sh["T"] = BEAT_T if i + 1 < n and shots[i + 1]["beat"] != sh["beat"] else INTRA_T
    shots[0]["at"] = 0.0
    imgs = [None if sh["still"].startswith("proc:") else Image.open(Path(stills) / sh["still"]).convert("RGB") for sh in shots]
    nframes = int(total * FPS)
    tmp = Path(out).with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(tmp)], stdin=subprocess.PIPE)

    def frame_of(i, tt):
        sh = shots[i]
        if imgs[i] is None:   # procedural shot: the animated end card
            return endcard(max(0.0, tt - sh["at"]), CFG["site"], CFG["cta"])
        u = (tt - sh["at"]) / max(1e-6, sh["end"] - sh["at"])
        z, cx, cy = camera(sh, min(max(u, 0), 1), i)
        src = imgs[i]
        for fx in sh.get("fx", []):
            src = apply_fx(src, fx, max(0.0, tt - sh["at"]))
        return view(src, z, cx, cy)

    for f in range(nframes):
        tt = f / FPS
        i = max(k for k in range(n) if shots[k]["at"] <= tt + 1e-9)
        sh = shots[i]
        if i + 1 < n and tt >= sh["end"] - sh["T"]:
            a = np.asarray(frame_of(i, min(tt, sh["end"] - 1e-3)), dtype=np.float32)
            b = np.asarray(frame_of(i + 1, tt), dtype=np.float32)
            frame = blend(a, b, sh["tr"], (tt - (sh["end"] - sh["T"])) / sh["T"])
        else:
            frame = np.asarray(frame_of(i, tt), dtype=np.float32)
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        if i + 1 < n and tt >= sh["end"] - sh["T"]:
            img = chip(img, sh["tr"], (tt - (sh["end"] - sh["T"])) / sh["T"])
        if not sh["notype"] or (i + 1 < n and tt >= sh["end"] - sh["T"] and not shots[i + 1]["notype"]):
            bt = beats[sh["beat"]]
            ov = type_overlay(bt["phrases"], tt, font, bt["start"] + bt["d"])
            if ov is not None:
                img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        ff.stdin.write(img.tobytes())
    ff.stdin.close()
    ff.wait()
    # sidecar captions from the script text on the spoken timings (never burned in)
    def tc(s):
        ms = int(s * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    cues = []
    for bt in beats:
        ws = re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", bt["vo"])).strip().split()
        ch = [ws[i:i + 6] for i in range(0, len(ws), 6)]
        for k, c in enumerate(ch):
            cues.append((bt["start"] + bt["d"] * k / len(ch), bt["start"] + bt["d"] * (k + 1) / len(ch), " ".join(c)))
    Path(out).with_suffix(".srt").write_text("".join(f"{i}\n{tc(a)} --> {tc(b)}\n{x}\n\n" for i, (a, b, x) in enumerate(cues, 1)))
    json.dump({"total": total, "shots": [{"still": sh["still"], "at": round(sh["at"], 2), "end": round(sh["end"], 2)} for sh in shots],
               "beats": [{"id": bt["id"], "start": round(bt["start"], 2), "dur": round(bt["d"], 2)} for bt in beats]},
              open(Path(out).with_suffix(".timeline.json"), "w"), indent=1)
    # audio: one mix recipe for every video (story_mix.py, levels in config.json "mix")
    story_mix.main(Path(out).with_suffix(".timeline.json"), vo_dir, tmp, out, music, sfx_files)
    print("OK", total, "s,", n, "shots,", out)


if __name__ == "__main__":
    argv, opts = sys.argv[1:], {}
    for key in ("--music", "--sfx"):
        if key in argv:
            i = argv.index(key)
            opts[key] = argv[i + 1].split(",") if key == "--sfx" else argv[i + 1]
            del argv[i:i + 2]
    if len(argv) != 4 or len(opts) != 2:
        sys.exit(__doc__)
    main(*argv, music=opts["--music"], sfx_files=opts["--sfx"])
