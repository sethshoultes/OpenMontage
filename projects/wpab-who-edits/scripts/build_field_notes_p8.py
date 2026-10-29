#!/usr/bin/env python3
"""Piece 8 of the field-notes series (memberintel-marketing#720, post #8803 / memberintel#8857): what AI can run for your
membership marketing. Silent, 1080x1920, everything between y=192 and y=1530, type 50 px or larger and near-white.
The numbers and their as-of dates live in field_notes_p8.json; edit it and re-render for the 11-24 refresh.

  build_field_notes_p8.py <data.json> <out.mp4>
"""
import json
import subprocess
import sys

from PIL import Image

from build_who_edits import ACCENT, BG, FPS, H, MARGIN, TEXT, W, block, paint, scene_text


def stack(items, y, gap=60):
    """items: [(start, element-builder(y))]; returns [(start, element)] laid out top to bottom from y."""
    out = []
    for t0, make, *after in items:  # an optional third value is the gap below this element
        el = make(y)
        out.append((t0, el))
        y = el[2] + (after[0] if after else gap)
    return out


def build(data_path, out):
    d = json.load(open(data_path))
    asof = f"As of {d['as_of']}"

    s1 = scene_text(stack([(0.3, lambda y: block("You run a membership.", 92, y, lead=1.12)),
                           (1.4, lambda y: block("Marketing lands in the same evenings as everything else.", 64, y, lead=1.2))], 480, 80), 5.0)
    s2 = scene_text(stack([(0.3, lambda y: block("So we tried AI on ourselves.", 100, y, lead=1.12)),
                           (1.6, lambda y: block(f"Since {d['since']}, on memberpress.ai", 58, y))], 520, 80), 5.0)

    h3 = block("What it did", 92, 250)
    sub3 = block(asof, 56, h3[2] + 20)
    items, y, t = [(0.3, h3), (0.6, sub3)], sub3[2] + 60, 1.4
    for num, label in [(d["scripts"], ["episode scripts on file;", f"the AI writer added at most {d['scripts_by_ai_max']}"]),
                       (d["blog_drafts"], ["changes to the blog", "by an AI drafter"]),
                       (d["x_posts"], ["posts on Opal's X account,", f"by {d['x_posts_by']}"])]:
        n = block(str(num), 110, y, fill=ACCENT)
        l = block(label, 54, n[2] - 6, lead=1.15)
        items += [(t, n), (t + 0.3, l)]
        y, t = l[2] + 40, t + 2.6
    s3 = scene_text(items, 11.0)

    s4 = scene_text(stack([(0.3, lambda y: block("On the blog", 84, y)), (0.6, lambda y: block(asof, 56, y)),
                           (1.2, lambda y: block(f"{d['posts_live']} posts live", 100, y, fill=ACCENT)),
                           (2.2, lambda y: block(f"with {d['videos']} short videos", 70, y))], 480, 50), 6.0)

    s5 = scene_text(stack([(0.3, lambda y: block("What it didn't do", 92, y)),
                           (1.3, lambda y: block(["Tell us whether it worked.", "We haven't looked yet."], 62, y, marker=("dash", ACCENT), lead=1.15)),
                           (3.4, lambda y: block("Switch itself off.", 62, y, marker=("dash", ACCENT), lead=1.15), 14),
                           (4.0, lambda y: block([f"Switched off {d['off_date']}.", f"Still off as of {d['as_of']}."], 54, y, lead=1.2, x=MARGIN + 62)),
                           (6.2, lambda y: block("Choose why we do this.", 62, y, marker=("dash", ACCENT), lead=1.15))], 300, 70), 10.5)

    s6 = scene_text(stack([(0.3, lambda y: block("Why we do this is one sentence. It's Seth's.", 70, y, lead=1.15)),
                           (1.6, lambda y: block("“" + d["sentence"] + "”", 74, y, fill=ACCENT, lead=1.2))], 420, 90), 8.0)

    s7 = scene_text(stack([(0.3, lambda y: block("Who does what", 92, y, lead=1.12)),
                           (1.4, lambda y: block(["AI carried the steady work:", "scripts, drafts,", "regular posts."], 62, y, marker=("check", ACCENT), lead=1.15)),
                           (3.6, lambda y: block(["People kept what's true,", "when to stop,", "and whether it works."], 62, y, marker=("check", ACCENT), lead=1.15)),
                           (5.8, lambda y: block("You know your members.", 70, y, fill=ACCENT, lead=1.15))], 300, 70), 8.5)

    s8 = scene_text(stack([(0.3, lambda y: block("MemberPress.ai", 100, y, fill=ACCENT)),
                           (1.0, lambda y: block(["helps you spend your week", "with your members,", "not in settings."], 62, y, lead=1.15))], 560, 70), 4.5)

    scenes = [(s1, 5.0), (s2, 5.0), (s3, 11.0), (s4, 6.0), (s5, 10.5), (s6, 8.0), (s7, 8.5), (s8, 4.5)]
    ff = subprocess.Popen(["nice", "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                          stdin=subprocess.PIPE)
    total = 0.0
    for draw, dur in scenes:
        for k in range(int(dur * FPS)):
            frame = Image.new("RGBA", (W, H), BG)
            draw(frame, k / FPS, dur)
            ff.stdin.write(frame.convert("RGB").tobytes())
        total += dur
    ff.stdin.close()
    ff.wait()
    print("OK", total, "s", out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(*sys.argv[1:])
