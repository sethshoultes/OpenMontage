"""Regression for misspelled video captions.

``build_short.py`` (the two-host social short builder) used to generate
captions by running free ASR transcription over the rendered narration audio
and trusting whatever words it guessed. ASR has never seen brand/product
vocabulary like "MembersIntel" or "MemberPress", so it reliably mis-transcribed
exactly the words that matter most, and those mis-transcriptions landed
directly in published captions.

``align_words_to_reference`` fixes this by treating the TTS input text (the
actual script — always correct by construction) as ground truth, and using
ASR only to estimate WHEN each of those words was spoken.
"""

from __future__ import annotations

import pytest

from tools.subtitle.caption_align import align_words_to_reference, normalize_word


def test_normalize_word_strips_punctuation_and_case():
    assert normalize_word("MembersIntel's") == "membersintel's"
    assert normalize_word("Hello,") == "hello"
    assert normalize_word("WORLD!") == "world"


def test_perfect_transcription_keeps_reference_words_and_asr_timing():
    reference = "Thirteen years working with the world's top membership sites".split()
    whisper = [(w, i * 0.4, i * 0.4 + 0.35) for i, w in enumerate(reference)]

    result = align_words_to_reference(whisper, reference)

    assert [w for w, _, _ in result] == reference
    assert result[0][0] == "Thirteen"
    assert result[0][1] == pytest.approx(0.0)
    assert result[0][2] == pytest.approx(0.35)
    assert result[-1][0] == "sites"
    assert result[-1][1] == pytest.approx(3.2)
    assert result[-1][2] == pytest.approx(3.55)


def test_mistranscribed_brand_word_keeps_correct_spelling():
    # Whisper hears "MembersIntel" as two garbled words ("member" + "cintel")
    # — the regression this test guards against: that mis-hearing must never
    # reach the caption text, only its timing span may be reused.
    reference = "MembersIntel reads your data".split()
    whisper = [
        ("member", 0.0, 0.3),
        ("cintel", 0.3, 0.7),
        ("reads", 0.7, 1.0),
        ("your", 1.0, 1.2),
        ("data", 1.2, 1.5),
    ]

    result = align_words_to_reference(whisper, reference)

    assert [w for w, _, _ in result] == reference
    assert result[0] == ("MembersIntel", 0.0, 0.7)


def test_word_asr_dropped_entirely_is_interpolated():
    # Whisper never detects "a" at all between "buys" and "month".
    reference = "the discount buys a month then they leave anyway".split()
    whisper = [
        ("the", 0.0, 0.2), ("discount", 0.2, 0.6), ("buys", 0.6, 0.9),
        ("month", 1.1, 1.4),
        ("then", 1.4, 1.6), ("they", 1.6, 1.8), ("leave", 1.8, 2.1), ("anyway", 2.1, 2.5),
    ]

    result = align_words_to_reference(whisper, reference)

    assert [w for w, _, _ in result] == reference
    missing = next(r for r in result if r[0] == "a")
    assert 0.9 <= missing[1] < missing[2] <= 1.1


def test_asr_hallucinated_word_is_dropped_not_inserted():
    # Whisper hears a filler ("um") that was never in the script.
    reference = "members who cancel on price".split()
    whisper = [
        ("members", 0.0, 0.3), ("who", 0.3, 0.5), ("um", 0.5, 0.6),
        ("cancel", 0.6, 0.9), ("on", 0.9, 1.0), ("price", 1.0, 1.3),
    ]

    result = align_words_to_reference(whisper, reference)

    assert [w for w, _, _ in result] == reference
    assert "um" not in [w for w, _, _ in result]


def test_empty_reference_returns_empty():
    assert align_words_to_reference([("hello", 0.0, 0.3)], []) == []


def test_empty_asr_still_returns_every_reference_word():
    # A silent or failed clip: no ASR signal at all. Every reference word
    # must still come back (spelling-correct captions matter more than
    # precise timing when there's no audio signal to time against).
    reference = "a targeted win back outperforms a discount".split()

    result = align_words_to_reference([], reference)

    assert [w for w, _, _ in result] == reference
    for _, start, end in result:
        assert start < end
