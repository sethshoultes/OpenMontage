"""Forced alignment of known-correct script text onto ASR-detected timing.

Free ASR transcription (e.g. Whisper) guesses both the words AND their
timing from audio. For a TTS-narrated video the words are already known —
they're whatever text was fed to the TTS provider — so there is no need to
trust ASR's guess at what was said, only its guess at WHEN each word lands.
Brand/product vocabulary an ASR model has never seen (e.g. "MembersIntel")
is exactly the vocabulary it most reliably mis-transcribes, which is how
misspelled captions were reaching production: captions were built from raw
ASR output instead of the source script.

Usage: pass the reference words (from the TTS input text, in order) and the
words+timestamps ASR actually detected for that same audio. Get back one
(word, start, end) tuple per reference word — correct spelling guaranteed by
construction, timing best-effort from the audio.
"""

from __future__ import annotations

import difflib
import re


def normalize_word(word: str) -> str:
    """Strip punctuation and case for alignment comparison only — the
    original reference word (with its own punctuation/case) is always what
    ends up in the returned captions, never this normalized form."""
    return re.sub(r"[^\w']", "", word).lower()


def align_words_to_reference(
    whisper_words: list[tuple[str, float, float]],
    reference_words: list[str],
) -> list[tuple[str, float, float]]:
    """Maps ASR-detected timing onto the known-correct reference words.

    whisper_words: (text, start_seconds, end_seconds) tuples as detected by
        an ASR pass over one clip of audio — the text is used only to align
        against reference_words, never returned.
    reference_words: the correct words actually spoken, in order (e.g. split
        from the exact text that was given to the TTS provider).

    Returns one (word, start_seconds, end_seconds) tuple per reference word.
    Where ASR detected a matching (or near-matching) span, timing comes from
    that span. Where ASR missed a reference word entirely, its timing is
    interpolated between its nearest aligned neighbors — still spelled
    correctly, just with an estimated rather than measured timestamp.
    """
    if not reference_words:
        return []

    wh_norm = [normalize_word(w[0]) for w in whisper_words]
    ref_norm = [normalize_word(w) for w in reference_words]
    sm = difflib.SequenceMatcher(None, wh_norm, ref_norm, autojunk=False)

    timed: list[tuple[float, float] | None] = [None] * len(reference_words)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                timed[j1 + k] = (whisper_words[i1 + k][1], whisper_words[i1 + k][2])
        elif tag == "replace" and i2 > i1:
            # ASR detected SOME words here, just not matching the reference
            # text exactly (mis-transcription) — spread that time span evenly
            # across the reference words it corresponds to.
            span_start, span_end = whisper_words[i1][1], whisper_words[i2 - 1][2]
            n = j2 - j1
            step = (span_end - span_start) / n
            for k in range(n):
                timed[j1 + k] = (span_start + step * k, span_start + step * (k + 1))
        # tag == "delete": ASR words with no reference counterpart (e.g. a
        # filler sound misheard as a word) — contribute nothing.
        # tag == "insert": reference words ASR never detected at all — left
        # as None here, filled in by interpolation below.

    n = len(timed)
    i = 0
    while i < n:
        if timed[i] is not None:
            i += 1
            continue
        j = i
        while j < n and timed[j] is None:
            j += 1
        prev_end = timed[i - 1][1] if i > 0 else (whisper_words[0][1] if whisper_words else 0.0)
        next_start = timed[j][0] if j < n else (whisper_words[-1][2] if whisper_words else prev_end)
        gap_words = j - i
        span = max(next_start - prev_end, 0.05 * gap_words)
        step = span / gap_words
        for k in range(gap_words):
            timed[i + k] = (prev_end + step * k, prev_end + step * (k + 1))
        i = j

    return [(reference_words[k], timed[k][0], timed[k][1]) for k in range(n)]
