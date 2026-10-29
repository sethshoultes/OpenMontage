#!/usr/bin/env python3
"""Audio mix for the story videos (sethshoultes.github.io#145, v3.1): the voice stays untouched, the
sound effects sit far under it and only land cuts, the music is ducked hard under speech and carries a
cool-to-warm arc. Every level is a number in config.json under "mix", and `report` measures the result.

  story_mix.py <timeline.json> <vo-dir> <silent.mp4> <out.mp4> --music bed.mp3 --sfx a.mp3,b.mp3

Reuses a finished picture (the .silent.mp4) so a mix change never touches the frames.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
MIX = json.load(open(HERE / "config.json"))["mix"]
SR = 48000
HOP = 0.05  # envelope resolution (s)


def decode(path, af=None):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path)] + (["-af", af] if af else []) + ["-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(cmd, check=True, capture_output=True).stdout, dtype=np.float32).copy()


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)


def lufs(x):
    """Integrated loudness of a mono float array, via ffmpeg ebur128."""
    p = subprocess.run(["ffmpeg", "-nostats", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", "ebur128", "-f", "null", "-"],
                       input=x.astype(np.float32).tobytes(), capture_output=True)
    for line in reversed(p.stderr.decode().splitlines()):
        if line.strip().startswith("I:"):
            return float(line.split()[1])
    raise SystemExit("ebur128 gave no loudness")


def place(buf, clip, t):
    i = int(t * SR)
    n = min(len(clip), len(buf) - i)
    if n > 0:
        buf[i:i + n] += clip[:n]


def smooth(env, attack, release):
    """One-pole follower on a gain envelope in dB: falls with `attack`, recovers with `release` (s)."""
    out, y = np.empty_like(env), env[0]
    ka, kr = np.exp(-HOP / attack), np.exp(-HOP / release)
    for i, v in enumerate(env):
        k = ka if v < y else kr
        y = k * y + (1 - k) * v
        out[i] = y
    return out


def mix(beats, total, music, sfx_files, turn_t, out_wav):
    n = int(total * SR)
    vo = np.zeros(n, np.float32)
    for b in beats:
        place(vo, decode(b["mp3"]), b["start"])
    # speech activity on the HOP grid, widened so the music is already down when a word starts
    hop = int(HOP * SR)
    frames = len(vo) // hop
    raw = np.array([rms_db(vo[i * hop:(i + 1) * hop]) > MIX["speech_floor_db"] for i in range(frames)])
    act = np.convolve(raw, np.ones(int(MIX["speech_pad_s"] / HOP) * 2 + 1), "same") > 0
    # music: a cool (thin, dark) and a warm (full, low-shelf) rendering, crossfaded at the turn
    cool = decode(music, "highpass=f=250,lowpass=f=2800")
    warm = decode(music, "equalizer=f=120:t=h:w=200:g=3,treble=g=1")
    cool, warm = (np.resize(a, n) if len(a) < n else a[:n] for a in (cool, warm))
    t = np.arange(frames) * HOP
    warmth = np.clip((t - (turn_t - MIX["turn_lead_s"])) / (MIX["turn_ramp_s"]), 0, 1)
    warmth = 0.5 - 0.5 * np.cos(np.pi * warmth)
    w_s = np.repeat(warmth, hop)[:n]
    w_s = np.pad(w_s, (0, n - len(w_s)), mode="edge")
    bed = cool * (1 - w_s) + warm * w_s
    bed = bed / (np.sqrt(np.mean(bed ** 2)) + 1e-9) * np.sqrt(np.mean(vo[np.abs(vo) > 1e-4] ** 2))  # bed rms == voice rms when speech is on
    # level relative to the voice: cool under the problem, a little warmer after the turn; louder with no speech
    speech_db = MIX["music_cool_db"] + (MIX["music_warm_db"] - MIX["music_cool_db"]) * warmth
    gap_db = np.where(t < turn_t, MIX["music_gap_cool_db"], MIX["music_gap_warm_db"])
    tail_t = max(b["start"] + b["d"] for b in beats)
    env = np.where(act, speech_db, gap_db)
    env = np.where(t > tail_t + 0.3, MIX["music_outro_db"], env)
    env = smooth(env, MIX["duck_attack_s"], MIX["duck_release_s"])
    g = np.repeat(10 ** (env / 20), hop)[:n]
    g = np.pad(g, (0, n - len(g)), mode="edge")
    fade = np.clip((total - np.arange(n) / SR) / MIX["fade_out_s"], 0, 1)
    music_bus = bed * g * fade
    # sfx: only on a beat change, inside the breath before the next line, never over a word
    sfx_bus = np.zeros(n, np.float32)
    cuts = []
    voice_lufs = lufs(vo)
    for q in range(1, len(beats)):
        tc = beats[q]["start"]
        prev_end = (np.flatnonzero(raw[:int(tc / HOP)])[-1] + 1) * HOP  # where the last spoken word actually stops
        t0 = max(tc - MIX["sfx_max_s"], prev_end + MIX["sfx_after_word_s"])
        if tc - t0 < MIX["sfx_min_s"]:
            continue
        clip = decode(sfx_files[(q - 1) % len(sfx_files)])
        clip = clip[-int((tc - t0) * SR):]  # the swell into the cut
        k = int(MIX["sfx_fade_s"] * SR)
        clip = clip * np.minimum(1, np.minimum(np.arange(len(clip)), np.arange(len(clip))[::-1]) / k)
        clip = clip / (np.sqrt(np.mean(clip ** 2)) + 1e-9) * np.sqrt(np.mean(vo[np.abs(vo) > 1e-4] ** 2)) * 10 ** (MIX["sfx_db"] / 20)
        place(sfx_bus, clip.astype(np.float32), t0)
        cuts.append((round(float(t0), 2), round(tc, 2)))
    total_mix = vo + sfx_bus + music_bus
    # one linear gain to the target loudness, then a ceiling (no pumping from a dynamic normaliser)
    gain_db = MIX["target_lufs"] - lufs(total_mix)
    scale = 10 ** (gain_db / 20)
    final = np.clip(total_mix * scale, -10 ** (MIX["true_peak_db"] / 20), 10 ** (MIX["true_peak_db"] / 20))
    stems = {"vo": vo * scale, "sfx": sfx_bus * scale, "music": music_bus * scale, "act": act, "cuts": cuts}
    Path(out_wav).write_bytes(final.astype(np.float32).tobytes())
    return final, stems


def report(stems, beats):
    vo, sfx, mus, act = stems["vo"], stems["sfx"], stems["music"], stems["act"]
    hop = int(HOP * SR)
    sp = np.array([a for a in range(len(act)) if act[a]])
    seg = lambda x: np.concatenate([x[i * hop:(i + 1) * hop] for i in sp])
    v, m = rms_db(seg(vo)), rms_db(seg(mus))
    print(f"speech windows: voice {v:.1f} dB, music {m:.1f} dB -> music {v - m:.1f} dB under the voice")
    # per beat: music under voice, and the sfx peak in any window where the voice is speaking
    for b in beats:
        i0, i1 = int(b["start"] * SR), int((b["start"] + b["d"]) * SR)
        print(f"  {b['id']}: music {rms_db(vo[i0:i1]) - rms_db(mus[i0:i1]):.1f} dB under the voice")
    over = 0.0
    for i in sp:
        s = sfx[i * hop:(i + 1) * hop]
        if np.any(np.abs(s) > 1e-5) and rms_db(vo[i * hop:(i + 1) * hop]) > MIX["speech_floor_db"] + 6:
            over = max(over, rms_db(s))
    print("sfx cuts (start, cut):", stems["cuts"], "| sfx under the voice:", f"{v - rms_db(sfx[np.abs(sfx) > 1e-6]):.1f} dB",
          "| loudest sfx inside speech:", "none" if over == 0 else f"{over:.1f} dB")


def main(timeline, vo_dir, silent, out, music, sfx_files):
    tl = json.load(open(timeline))
    picked = json.load(open(Path(vo_dir) / "picked.json"))
    beats = []
    for b in tl["beats"]:
        mp3 = Path(vo_dir) / picked["s" + b["id"][1:]]["file"]
        beats.append({"id": b["id"], "start": b["start"], "d": b["dur"], "mp3": mp3})
    turn_t = next(b["start"] for b in beats if b["id"] == MIX["turn_beat"])
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "mix.f32"
        final, stems = mix(beats, tl["total"], music, sfx_files, turn_t, wav)
        report(stems, beats)
        aud = Path(out).with_suffix(".audio.m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(wav), "-ac", "2",
                        "-c:a", "aac", "-b:a", "192k", str(aud)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(aud), "-c:v", "copy", "-c:a", "copy", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)
    print("OK", out)


if __name__ == "__main__":
    a = sys.argv[1:]
    opts = {k: a[a.index(k) + 1] for k in ("--music", "--sfx") if k in a}
    if len(a) < 4 or "--music" not in opts or "--sfx" not in opts:
        sys.exit(__doc__)
    main(a[0], a[1], a[2], a[3], opts["--music"], opts["--sfx"].split(","))
