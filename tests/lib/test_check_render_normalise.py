"""Regression test for check_render.normalise() on spoken numbers (circuit-city#114).

The narration-alignment check transcribes each section with Whisper and compares it to the script.
The scripts spell numbers the way a person says them; Whisper writes the numeral. normalise() already
met that for 0-20 and four-digit years, but "thirty-one years" was heard as "31 years" and "a hundred
and fifty projects" as "150 projects", and beats carrying one scored 0.88 against a 0.90 threshold
with the audio correct. Each assertion below has a control: the near-miss number must NOT match.
"""

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "check_render", PROJECT_ROOT / "projects" / "ohmsville-classroom" / "scripts" / "check_render.py"
)
check_render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_render)
normalise = check_render.normalise
align = check_render.align


def test_a_spelled_two_digit_number_lines_up_with_its_numeral():
    assert normalise("for thirty-one years") == normalise("for 31 years")
    assert normalise("for thirty-one years") != normalise("for 32 years")
    assert normalise("ninety nine percent") == normalise("99 percent")


def test_a_spelled_three_digit_number_lines_up_with_its_numeral():
    assert normalise("a hundred and fifty projects apiece") == normalise("150 projects apiece")
    assert normalise("one hundred fifty projects") == normalise("150 projects")
    assert normalise("two hundred and five") == normalise("205")
    assert normalise("two hundred and five") != normalise("250")
    assert normalise("a hundred and fifty") != normalise("115")


def test_a_round_number_and_a_bare_hundred_line_up():
    assert normalise("a hundred times") == normalise("100 times")
    assert normalise("two hundred times") == normalise("200 times")
    assert normalise("sixty miles") == normalise("60 miles")


def test_an_and_that_is_not_part_of_the_number_is_kept():
    assert normalise("a hundred and the rest") == normalise("100 and the rest")
    assert normalise("a hundred and the rest") != normalise("100 the rest")


def test_numbers_that_already_matched_still_match():
    # 0-20 were words on both sides before
    assert normalise("thirteen and a half hours") == normalise("13 and a half hours")
    assert normalise("twenty years") == normalise("20 years")
    # a spoken year, whose low pair is itself a two-digit number
    assert normalise("eighteen forty-one") == normalise("1841")
    assert normalise("eighteen forty-one") != normalise("1842")
    assert normalise("eighteen hundred") == normalise("1800")


def test_the_alignment_still_rejects_the_wrong_take():
    script = "I fixed televisions in this town for thirty-one years, and this is the shop."
    assert align(script, "I fixed televisions in this town for 31 years, and this is the shop.") == 1.0
    assert align(script, "Breathe in: solder, hot dust, and the cardboard the kits come in.") < 0.6


# --- circuit-city#117: Whisper's repetition tail --------------------------------------------------
# At the end of a clip Whisper can repeat the last sentence, stamping every repeated word onto the final
# instant: Founders s13 had 21 words between 25.10 s and 25.10 s of a 25.12 s clip, the last 20 of them
# zero-length. Nobody speaks 20 words in no time, so a trailing run of zero-length words is not speech.
spoken_words = check_render.spoken_words


def _w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_a_trailing_run_of_zero_length_words_is_not_speech():
    words = [_w(" a", 0.0, 0.2), _w(" b", 0.2, 0.4), _w(" c", 0.4, 0.6),
             _w(" c", 0.6, 0.6), _w(" d", 0.6, 0.6), _w(" e", 0.6, 0.6)]
    assert spoken_words(words).split() == ["a", "b", "c"]


def test_a_zero_length_word_inside_the_clip_is_kept():
    # only a run that reaches the end of the list is dropped: a stray zero-length word mid-clip is real
    words = [_w(" a", 0.0, 0.2), _w(" b", 0.2, 0.2), _w(" c", 0.2, 0.4), _w(" d", 0.4, 0.6)]
    assert spoken_words(words).split() == ["a", "b", "c", "d"]


def test_nothing_is_dropped_from_a_clip_with_real_timings_to_the_end():
    words = [_w(" a", 0.0, 0.2), _w(" b", 0.2, 0.4), _w(" c", 0.4, 0.6)]
    assert spoken_words(words).split() == ["a", "b", "c"]
    assert spoken_words([]) == ""


def test_a_clip_that_is_only_zero_length_words_is_empty_not_an_error():
    assert spoken_words([_w(" a", 1.0, 1.0), _w(" b", 1.0, 1.0)]) == ""


def test_the_tail_no_longer_fails_a_correct_section_and_a_real_repeat_still_does():
    script = "Thirteen and a half hours is a laboratory result, not something you sell a family. Lewis Latimer patented a way of making filaments."
    said = [_w(f" {t}", i * 0.3, i * 0.3 + 0.28) for i, t in enumerate(
        "13 and a half hours is a laboratory result, not something you sell a family. Lewis Latimer patented a way of making filaments.".split())]
    tail_at = said[-1]["end"]
    echo = [_w(f" {t}", tail_at, tail_at) for t in
            "13 and a half hours is a laboratory result, not something you sell a family, not something you sell a family.".split()]
    with_tail = " ".join(w["word"] for w in said + echo)
    assert align(script, with_tail) < 0.9                    # the bug: a correct take fails
    assert align(script, spoken_words(said + echo)) >= 0.99  # the fix
    # control: the same words spoken twice with real timings are a real repeat and still score low
    spoken_twice = said + [_w(w["word"], tail_at + k * 0.3, tail_at + k * 0.3 + 0.28) for k, w in enumerate(echo)]
    assert align(script, spoken_words(spoken_twice)) < 0.9
