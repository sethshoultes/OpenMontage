"""Voiceover for a silent cut, in Seth's ElevenLabs clone on eleven_v3, timed to the cut's slots.

Usage: gen_vo_v3.py <narration.json> <out-dir> [total_seconds]
narration.json: {"lines": [{"id": "n01", "start": 0.0, "slot": 6.5, "text": "[warmly] You run a membership site..."}, ...]}
  `start` is where the line should begin in the cut; `slot` is the longest it may run (seconds, up to the next line's start minus a breath).
Text keeps eleven_v3 audio tags such as [warmly], [short pause]; they are stripped for the speech check and the word times.
Three takes per line (stability 0.3 / 0.5 / 0.7); a line with no eligible take gets up to five more. A take is eligible when its median pitch is within 12% of REF_F0 (Seth's own ~130 Hz),
it fits its slot, and the speech check hears the script's words (at most 2 differing words). Among eligible takes the one with the
least silence inside the line wins, then the liveliest. Writes <id>-tN.mp3/.json, picked.json, and narration.wav (every line placed at its
start on one timeline of total_seconds). ONE job at a time (fleet rule): the speech check is a single faster-whisper pass per take.
Env: ELEVENLABS_API_KEY.
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from stt_check import diff_words  # noqa: E402
from vo_metrics import metrics  # noqa: E402

CFG = json.load(open(HERE / "config.json"))
REF_F0 = 130.0
TARGET_LUFS = -19.0
STABILITY = (0.3, 0.5, 0.7, 0.4, 0.6, 0.5, 0.35, 0.65)   # the first three always; more only for a line with no eligible take yet
TAG = re.compile(r"\[[^\]]*\]")


def plain(text):
    return re.sub(r"\s+", " ", TAG.sub("", text)).strip()


def tts(text, out, stability):
    body = {"text": text, "model_id": "eleven_v3",
            "voice_settings": {"stability": stability, "similarity_boost": 0.9, "style": 0.3, "use_speaker_boost": True}}
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{CFG['voice_id']}/with-timestamps?output_format=mp3_44100_128",
        json.dumps(body).encode(), {"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    Path(str(out) + ".mp3").write_bytes(base64.b64decode(r["audio_base64"]))
    json.dump(r["alignment"], open(str(out) + ".json", "w"))


def take_quality(path):
    """(tail_ok, level_dbfs): the last 30 ms must be quiet (a take that ends mid-word is clipped) and the speech must not be a whisper."""
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float)) / 32768
    tail = a[-480:].mean()
    live = a[a > 0.02]
    speech = live.mean() if len(live) else 1.0
    level = 20 * np.log10(np.sqrt(np.mean(live ** 2)) + 1e-9) if len(live) else -99
    return tail < 0.2 * speech, level   # still at speech level in the last 30 ms: the take ends mid-sound


def inner_silence(path):
    """(silence inside the line, speech span, seconds the assembly will take out by shortening pauses over 0.7 s to 0.55 s)."""
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float))
    a /= a.max()
    env = a[: len(a) // 160 * 160].reshape(-1, 160).mean(1)
    live = np.where(env > 0.02)[0]
    lo, hi = live[0], live[-1]
    total = excess = cur = 0
    for i in range(lo, hi + 1):
        if env[i] < 0.02:
            cur += 1
        else:
            if cur >= 45:
                total += cur / 100
            if cur >= 70:
                excess += (cur - 55) / 100
            cur = 0
    return total, (hi - lo) / 100, excess


def shorten_pauses(src, dst, keep=0.55, min_run=0.7):
    """Write dst (44.1 kHz mono wav) with every silence inside the line that is longer than min_run cut down to `keep` seconds."""
    sr = 44100
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(src), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16)
    a = np.abs(x.astype(float))
    a /= a.max()
    hop = sr // 100
    env = a[: len(a) // hop * hop].reshape(-1, hop).mean(1)
    live = np.where(env > 0.02)[0]
    lo, hi = live[0], live[-1]
    runs, i = [], lo
    while i <= hi:
        if env[i] < 0.02:
            j = i
            while j <= hi and env[j] < 0.02:
                j += 1
            if (j - i) >= int(min_run * 100):
                runs.append((i * hop, j * hop))
            i = j
        else:
            i += 1
    half = int(keep * sr) // 2
    pieces, pos = [], 0
    for r0, r1 in runs:
        pieces.append(x[pos:r0 + half])   # speech, then half of the kept silence
        pos = r1 - half                   # resume half a kept silence before the next speech
    pieces.append(x[pos:])
    y = np.concatenate(pieces)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-", str(dst)], input=y.tobytes(), check=True)


def main(narr, outdir, total=None):
    from faster_whisper import WhisperModel
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    lines = json.load(open(narr))["lines"]
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    picked = {}
    failed = []
    for ln in lines:
        rows = []
        n = 0
        while n < len(STABILITY):
            n += 1
            if n > 3 and any(r[0] for r in rows):
                break
            stab = STABILITY[n - 1]
            p = out / f"{ln['id']}-t{n}"
            if not Path(str(p) + ".mp3").exists():
                tts(ln["text"], p, stab)
            m = metrics(str(p) + ".mp3")
            sil, speech, excess = inner_silence(str(p) + ".mp3")
            segs, _ = model.transcribe(str(p) + ".mp3", language="en", beam_size=5)
            heard = " ".join(s.text for s in segs).strip()
            diff = diff_words(plain(ln["text"]), heard)
            ok_f0 = abs(m["f0_med"] - REF_F0) / REF_F0 <= 0.12
            fits = m["secs"] - excess <= ln["slot"]   # after the assembly shortens long pauses
            tail_ok, level = take_quality(str(p) + ".mp3")
            ok = ok_f0 and fits and diff <= ln.get("max_diff", 2) and tail_ok and level > -30
            print(ln["id"], f"t{n}", f"{m['secs'] - excess:.2f}s/{ln['slot']:.1f}", f"f0 {m['f0_med']}", f"gaps {sil:.2f}", f"diff {diff}", "OK" if ok else
                  ("OFF-VOICE" if not ok_f0 else "TOO-LONG" if not fits else "CLIPPED-END" if not tail_ok else "QUIET" if level <= -30 else "MISREAD"), f"lvl {level:.0f}")
            rows.append((ok, -(sil - excess), m["spread_st"] + 0.35 * m["range_p10_p90_st"], n, m["secs"] - excess, heard))
        good = [r for r in rows if r[0]]
        if not good:
            failed.append(ln["id"])
            print(f"  {ln['id']}: NO ELIGIBLE TAKE (on-voice + fits {ln['slot']} s + reads the script); shorten the line or widen the slot")
            continue
        best = max(good, key=lambda r: (r[1], r[2]))
        picked[ln["id"]] = {"take": best[3], "file": f"{ln['id']}-t{best[3]}.mp3", "secs": best[4], "start": ln["start"]}
    if failed:
        sys.exit("lines without an eligible take: " + ", ".join(failed))
    json.dump(picked, open(out / "picked.json", "w"), indent=1)
    # assembly: each line has its long inner pauses shortened to ~0.55 s, is levelled to TARGET_LUFS and gets short fades; then one timeline
    proc = out / "proc"
    proc.mkdir(exist_ok=True)
    inputs, filt, labels = [], [], []
    for i, ln in enumerate(lines):
        src = out / picked[ln["id"]]["file"]
        dst = proc / f"{ln['id']}.wav"
        shorten_pauses(src, dst)
        r = subprocess.run(["ffmpeg", "-nostats", "-i", str(dst), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
        lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
        gain = max(-12.0, min(12.0, TARGET_LUFS - lufs))
        dur = float(subprocess.check_output(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(dst)]).strip())
        fin = proc / f"{ln['id']}.lv.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(dst), "-af", f"volume={gain}dB,afade=t=in:d=0.015,afade=t=out:st={dur - 0.04:.3f}:d=0.04", str(fin)], check=True)
        print(ln["id"], f"line {dur:.2f}s (take {picked[ln['id']]['secs']:.2f}s) level {lufs:.1f} -> {TARGET_LUFS} LUFS (gain {gain:+.1f} dB)")
        if dur > ln["slot"]:
            sys.exit(f"{ln['id']}: {dur:.2f}s after pause shortening is still over its {ln['slot']} s slot")
        inputs += ["-i", str(fin)]
        ms = int(ln["start"] * 1000)
        filt.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    mix = "".join(labels) + f"amix=inputs={len(lines)}:normalize=0[m]"
    if total:
        mix += f";[m]apad=whole_dur={total}[o]"
    last = "[o]" if total else "[m]"
    mix += f";{last}alimiter=limit=0.89:level=disabled[f]"   # nothing above about -1 dBFS
    last = "[f]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt) + ";" + mix, "-map", last,
                    "-ar", "44100", "-ac", "1", str(out / "narration.wav")], check=True)
    print("ok", out / "narration.wav")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) not in (2, 3):
        sys.exit(__doc__)
    main(a[0], a[1], float(a[2]) if len(a) == 3 else None)
