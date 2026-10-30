#!/usr/bin/env python3
"""Piece 8 of the field-notes series (memberintel-marketing#720, post #8803 / memberintel#8857): what AI can run for your
membership marketing. Silent, 1080x1920, everything between y=192 and y=1530, type 52 px or larger and near-white, every
slide's stack centred in the band. Built around what the owner gets, with two rounded numbers computed from the data file.
The numbers and their as-of dates live in field_notes_p8.json; edit it and re-render for the 11-24 refresh.

  build_field_notes_p8.py <data.json> <out.mp4>
"""
import json
import subprocess
import sys

from PIL import Image

from build_who_edits import ACCENT, BG, FPS, H, W, T, paint, scene_text, stack


def about(n, step):
    """A rounded count for the screen ('about 90'); a figure that is already round is shown as it is. The exact figure stays in the data file."""
    r = int(round(n / step)) * step
    return str(n) if n % step == 0 else f"about {r}"


def build(data_path, out):
    d = json.load(open(data_path))
    asof = f"As of {d['as_of']}"

    s1 = scene_text(stack([T(0.3, "You run a membership.", 124, lead=1.12, center=True, width=900),
                           T(1.0, "Marketing lands in the same evenings as everything else.", 88, lead=1.2, center=True, width=900)], gap=90), 5.8)
    s2 = scene_text(stack([T(0.3, "So we tried AI on ourselves.", 128, lead=1.12, center=True, width=900),
                           T(1.0, f"Since {d['since']}, on memberpress.ai", 82, lead=1.2, center=True, width=900)], gap=90), 6.3)

    s3 = scene_text(stack([T(0.3, "What AI did for us", 96, center=True, width=900),
                           T(0.6, asof, 60, bold=False, center=True, width=900),
                           T(1.2, "It wrote some of our video scripts,", 90, lead=1.15, center=True, width=900),
                           T(2.2, "drafted blog posts,", 90, lead=1.15, center=True, width=900),
                           T(3.2, "and posted for Opal, our assistant.", 90, lead=1.15, center=True, width=900)], gap=50), 8.7)

    s3b = scene_text(stack([T(0.3, f"{d['x_posts']} posts", 128, fill=ACCENT, center=True, width=900),
                            T(0.8, f"on Opal's X account, by {d['x_posts_by']}.", 84, lead=1.2, center=True, width=900)], gap=70), 6.2)

    s4 = scene_text(stack([T(0.3, "On the blog", 118, center=True, width=900),
                           T(0.8, f"{asof}: {d['posts_live']} posts live, and {d['videos']} short videos on them.", 88, lead=1.2, center=True, width=900)], gap=80), 6.2)

    s5 = scene_text(stack([T(0.3, "What it didn't do", 100, center=True, width=900),
                           T(0.6, asof, 60, bold=False, center=True, width=900),
                           T(1.4, "It didn't tell us whether it worked. We haven't looked yet.", 80, lead=1.2, center=True, width=900),
                           T(3.4, f"We turned off the video writer on {d['writer_off_date']}. The blog drafter was off by {d['as_of']}.", 72, lead=1.2, center=True, width=900)], gap=64), 9.0)

    # four balanced rows, each on one line at this size; "using AI tools." stays together (no lone "tools.")
    w = d["sentence"].split()
    assert d["sentence"] == "Helping business owners succeed with their membership business, using AI tools.", "re-break the quote for the new sentence"
    quote = ["\u201cHelping business owners", "succeed with their", "membership business,", "using AI tools.\u201d"]
    s6 = scene_text(stack([T(0.3, "The part AI didn't choose is why we do this. It's one sentence, and it's Seth's.", 72, lead=1.2, center=True, width=900),
                           T(1.0, quote, 64, fill=ACCENT, lead=1.2, center=True, width=900)], gap=80), 8.0)

    s7 = scene_text(stack([T(0.3, "Who does what", 116, center=True, width=900),
                           T(0.8, ["AI carried the steady work:", "scripts, drafts, regular posts."], 70, lead=1.15, center=True, width=900),
                           T(1.8, ["People kept what's true,", "when to stop,", "and whether it works."], 70, lead=1.15, center=True, width=900),
                           T(2.8, "You know your members.", 96, fill=ACCENT, lead=1.15, center=True, width=900),
                           T(3.8, "If your marketing looks like ours, that split may fit yours too.", 62, lead=1.2, center=True, width=900)], gap=52), 11.0)

    s8 = scene_text(stack([T(0.3, "MemberPress.ai", 104, fill=ACCENT, center=True, width=900),
                           T(0.9, ["helps you spend your week", "with your members,", "not in settings."], 84, lead=1.15, center=True, width=900)], gap=80), 5.8)

    scenes = [(s1, 5.8), (s2, 6.3), (s3, 8.7), (s3b, 6.2), (s4, 6.2), (s5, 9.0), (s6, 8.0), (s7, 11.0), (s8, 5.8)]
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
