"""Designed motion explainer from a story file: one concept still per narration beat, camera moves, real transitions,
kinetic type timed to the voice, a ducked music bed (v3 of the page video, sethshoultes.github.io#145).

Usage: build_story_video.py <story.json> <stills-dir> <vo-dir> <out.mp4> [--music bed.mp3] [--bg <dir with flow-sweep.webm, orb-form.webm>] [--sfx a.mp3,b.mp3]
  story.json   shots[]: id, vo, still, transition, kinetic [[text, anchor word]], cam [[t, zoom, cx, cy]] (see stories/)
  stills-dir   <id>.png per shot, 16:9, 2k or larger (made on Higgsfield / Nano Banana Pro; see the story's image prompts)
  vo-dir       picked.json + <id>-tN.mp3/.json from gen_vo.py (the takes' character timings drive the type)
Everything visual is drawn per frame here (crop, transition, type), so edges stay pin-sharp: no upscaler, no blur, no glow.
The data-flow scene and the orb (recorded from the site's own page by scripts/bg/record_flow_bg.mjs) are screen-blended over
the transitions as connective tissue, and the orb forms under the last shot. Captions are written as a sidecar .srt, never burned in.
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
CFG = json.load(open(HERE / "config.json"))
W, H, FPS = 1920, 1080, 30
T = 0.5                       # transition length (s)
GAP = 0.18                    # breath after each line
LEAD = 0.35
TAIL = 3.2
HOLD_MIN, HOLD_MAX = 1.5, 2.0 # a kinetic title stays 1.5 to 2 s unless the next one arrives first
BG = (11, 13, 16)
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
        pts = [[0, 1.0, 0.5 - 0.03 * side, 0.5], [1, 1.12, 0.5 + 0.03 * side, 0.49]]
    for a, b in zip(pts, pts[1:]):
        if u <= b[0]:
            k = ease((u - a[0]) / max(1e-6, b[0] - a[0]))
            return tuple(a[i] + (b[i] - a[i]) * k for i in (1, 2, 3))
    return tuple(pts[-1][1:])


def view(img, z, cx, cy):
    w, h = img.size
    cw, ch = w / z, h / z
    x0 = min(max(cx * w - cw / 2, 0), w - cw)
    y0 = min(max(cy * h - ch / 2, 0), h - ch)
    art = img.transform((ART_W, ART_H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
    canvas = Image.new("RGB", (W, H), BG)
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


def type_overlay(phrases, t, font):
    """RGBA kinetic title for time t: the active phrase pops in word by word, holds, then rises and fades."""
    act = None
    for i, (text, t0) in enumerate(phrases):
        t1 = phrases[i + 1][1] if i + 1 < len(phrases) else 1e9
        end = min(t1, t0 + HOLD_MAX) if t1 - t0 >= HOLD_MIN else t1
        if t0 <= t < end + 0.25:
            act = (text, t0, end)
    if not act:
        return None
    text, t0, end = act
    words = text.split()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    widths = [d.textlength(w + " ", font=font) for w in words]
    x0, y0 = ART_X + 28, ART_H + 12
    fade = 1.0 if t < end else max(0, 1 - (t - end) / 0.25)
    rise = 0 if t < end else int(24 * (t - end) / 0.25)
    d.rectangle((ART_X - 6, y0 + 10, ART_X + 4, y0 + 96), fill=ORANGE + (int(255 * fade),))
    x = x0
    for idx, (w, wd) in enumerate(zip(words, widths)):
        k = ease((t - t0 - 0.07 * idx) / 0.16)
        if k > 0:
            yoff = int((1 - k) * 30) - rise
            d.text((x, y0 + yoff), w, font=font, fill=(255, 255, 255, int(255 * k * fade)))
        x += wd
    return layer


def stream(path, ss, loop=True):
    """Generator of 1920x1080 RGB frames at 30 fps from a recording; loops when it ends."""
    while True:
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(ss), "-i", str(path), "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        while True:
            raw = p.stdout.read(W * H * 3)
            if len(raw) < W * H * 3:
                break
            yield np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 3)
        p.wait()
        if not loop:
            return


def screen(a, b, w):
    """Screen-blend b over a at weight w: only brightens, so the dark recording leaves the art untouched."""
    return 255 - (255 - a) * (255 - b * w) / 255


def main(story_path, stills, vo_dir, out, music=None, bg_dir=None, sfx_files=None):
    story = json.load(open(story_path))
    picked = json.load(open(Path(vo_dir) / "picked.json"))
    shots = story["shots"]
    font = ImageFont.truetype(FONT, 84, index=1)
    # timeline: each line starts after the last one plus a breath; a shot lasts its line
    starts, t = [], LEAD
    info = []
    for s in shots:
        pk = picked[s["id"]]
        mp3 = Path(vo_dir) / pk["file"]
        d = dur(mp3)
        al = json.load(open(str(mp3)[:-4] + ".json"))
        wt = word_times(al)
        starts.append(t)
        info.append({"mp3": mp3, "d": d, "words": wt, "start": t})
        t += d + GAP
    total = round(t + TAIL, 2)
    starts_v = [0.0] + [info[i]["start"] - 0.0 for i in range(1, len(shots))]
    # kinetic phrases in absolute time, anchored on the spoken word
    for s, inf in zip(shots, info):
        ph, j = [], 0
        for text, anchor in s["kinetic"]:
            k = next((i for i in range(j, len(inf["words"])) if inf["words"][i][0].startswith(anchor.lower())), None)
            ph.append((text, inf["start"] + (inf["words"][k][1] if k is not None else 0.0)))
            j = (k or j) + 1
        inf["phrases"] = ph
    imgs = [Image.open(Path(stills) / s["still"]).convert("RGB") for s in shots]
    n = len(shots)
    # shot i is on screen [bound[i], bound[i+1]); a transition of T seconds ends at bound[i+1] and begins T earlier
    bound = [0.0] + [info[i]["start"] for i in range(1, n)] + [total]
    nframes = int(total * FPS)
    flow = stream(Path(bg_dir) / "flow-sweep.webm", 1.5) if bg_dir else None
    orb = stream(Path(bg_dir) / "orb-form.webm", 5.5, loop=False) if bg_dir else None
    orb_t0 = bound[n - 1] + 0.2
    trans_windows = [(bound[k + 1] - T - 0.15, bound[k + 1] + 0.25) for k in range(n - 1)]
    tmp = Path(out).with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(tmp)], stdin=subprocess.PIPE)

    def frame_of(i, tt):
        u = (tt - bound[i]) / max(1e-6, bound[i + 1] - bound[i])
        z, cx, cy = camera(shots[i], min(max(u, 0), 1), i)
        return view(imgs[i], z, cx, cy)

    for f in range(nframes):
        tt = f / FPS
        i = max(k for k in range(n) if bound[k] <= tt + 1e-9)
        nxt = i + 1 < n and tt >= bound[i + 1] - T
        if nxt:
            a = np.asarray(frame_of(i, min(tt, bound[i + 1] - 1e-3)), dtype=np.float32)
            b = np.asarray(frame_of(i + 1, tt), dtype=np.float32)
            frame = blend(a, b, shots[i]["transition"], (tt - (bound[i + 1] - T)) / T)
        else:
            frame = np.asarray(frame_of(i, tt), dtype=np.float32)
        if flow is not None:
            fl = next(flow)
            wgt = 0.0
            for a0, b0 in trans_windows:
                if a0 <= tt <= b0:  # a soft ramp in and out around each transition
                    wgt = 0.75 * math.sin(math.pi * (tt - a0) / (b0 - a0)) ** 1.5
            if wgt > 0.01:
                frame = screen(frame, fl.astype(np.float32), wgt)
            if tt >= orb_t0:
                ob = next(orb, None)
                if ob is not None:
                    frame = screen(frame, ob.astype(np.float32), min(1.0, 0.95 * ease((tt - orb_t0) / 0.8)))
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        for inf in info:
            if inf["phrases"] and inf["start"] - 0.1 <= tt <= inf["start"] + inf["d"] + 1.0:
                ov = type_overlay(inf["phrases"], tt, font)
                if ov is not None:
                    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
                break
        ff.stdin.write(img.tobytes())
    ff.stdin.close()
    ff.wait()
    # audio: the voice at each start, music ducked under it
    ins, fl = [], []
    for k, inf in enumerate(info):
        ins += ["-i", str(inf["mp3"])]
        ms = int(inf["start"] * 1000)
        fl.append(f"[{k}:a]adelay={ms}|{ms},volume=1.0[v{k}]")
    fl.append("".join(f"[v{k}]" for k in range(n)) + f"amix=inputs={n}:normalize=0,apad=whole_dur={total}[vo]")
    if music:
        ins += ["-i", str(music)]
    sfx = [(sfx_files[k % len(sfx_files)], bound[k + 1] - T) for k in range(n - 1)] if sfx_files else []
    if sfx:
        for q, (k, tw) in enumerate(sfx):
            ins += ["-i", str(k)]
            ms = int(tw * 1000)
            fl.append(f"[{n + (1 if music else 0) + q}:a]adelay={ms}|{ms},volume=0.5[x{q}]")
        fl.append("".join(f"[x{q}]" for q in range(len(sfx))) + f"amix=inputs={len(sfx)}:normalize=0,apad=whole_dur={total}[sfxbus]")
        fl.append("[vo][sfxbus]amix=inputs=2:normalize=0[vo]")
    if music:
        fl.append(f"[{n}:a]atrim=0:{total},volume=0.55,afade=t=out:st={total - 2.5}:d=2.5[m];[vo]asplit[vo1][vo2];"
                  f"[m][vo1]sidechaincompress=threshold=0.02:ratio=9:attack=15:release=350[md];[vo2][md]amix=inputs=2:normalize=0[mix]")
        last = "mix"
    else:
        last = "vo"
    fl.append(f"[{last}]loudnorm=I=-16:TP=-1.5:LRA=9[aout]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fl), "-map", "[aout]", "-c:a", "aac", "-b:a", "192k",
                    str(Path(out).with_suffix(".audio.m4a"))], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-i", str(Path(out).with_suffix(".audio.m4a")), "-c:v", "copy", "-c:a", "copy",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    # sidecar captions from the script text on the spoken timings (never burned in)
    def tc(s):
        ms = int(s * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    cues = []
    for s, inf in zip(shots, info):
        ws = re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", s["vo"])).strip().split()
        ch = [ws[i:i + 6] for i in range(0, len(ws), 6)]
        for k, c in enumerate(ch):
            cues.append((inf["start"] + inf["d"] * k / len(ch), inf["start"] + inf["d"] * (k + 1) / len(ch), " ".join(c)))
    Path(out).with_suffix(".srt").write_text("".join(f"{i}\n{tc(a)} --> {tc(b)}\n{x}\n\n" for i, (a, b, x) in enumerate(cues, 1)))
    json.dump({"total": total, "shots": [{"id": s["id"], "start": round(inf["start"], 2), "dur": round(inf["d"], 2)} for s, inf in zip(shots, info)]},
              open(Path(out).with_suffix(".timeline.json"), "w"), indent=1)
    print("OK", total, out)


if __name__ == "__main__":
    argv, opts = sys.argv[1:], {}
    for key in ("--music", "--bg", "--sfx"):
        if key in argv:
            i = argv.index(key)
            opts[key] = argv[i + 1].split(",") if key == "--sfx" else argv[i + 1]
            del argv[i:i + 2]
    if len(argv) != 4:
        sys.exit(__doc__)
    main(*argv, music=opts.get("--music"), bg_dir=opts.get("--bg"), sfx_files=opts.get("--sfx"))
