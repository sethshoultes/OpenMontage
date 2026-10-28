"""Rough liveliness numbers for a voice take, so three takes can be ranked without a listener (not a replacement for ears).

Usage: vo_metrics.py take.mp3 [take2.mp3 ...]
Prints: seconds, F0 median (Hz), pitch spread (semitone std and p10-p90 range), loudness range (LU), words per second if a
.json alignment sits beside the take. Higher spread and range read as livelier; a take with a spread under about 2
semitones reads flat. Pitch is a plain autocorrelation over 40 ms frames on voiced frames only.
"""
import json
import os
import subprocess
import sys

import numpy as np


def f0_track(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    n, hop = int(0.04 * sr), int(0.01 * sr)
    gate = 0.12 * np.sqrt((x ** 2).mean()) + 1e-6
    lo, hi = int(sr / 300), int(sr / 70)
    out = []
    for i in range(0, len(x) - n, hop):
        fr = x[i:i + n] * np.hanning(n)
        if np.sqrt((fr ** 2).mean()) < gate:
            continue
        ac = np.correlate(fr, fr, "full")[n - 1:]
        if ac[0] <= 0:
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] / ac[0] > 0.45:
            out.append(sr / k)
    return np.array(out), len(x) / sr


def lra(path):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    for line in r.splitlines()[::-1]:
        if "LRA:" in line:
            return float(line.split("LRA:")[1].split()[0])
    return float("nan")


def metrics(path):
    f0, secs = f0_track(path)
    st = 12 * np.log2(f0 / np.median(f0))
    words = None
    j = os.path.splitext(path)[0] + ".json"
    if os.path.exists(j):
        chars = "".join(json.load(open(j))["characters"])
        words = len(chars.split()) / secs
    return {"secs": round(secs, 2), "f0_med": round(float(np.median(f0))), "spread_st": round(float(st.std()), 2),
            "range_p10_p90_st": round(float(np.percentile(st, 90) - np.percentile(st, 10)), 2), "lra_lu": lra(path),
            "words_per_s": None if words is None else round(words, 2)}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(os.path.basename(p), metrics(p))
