"""Turn one ADR markdown into adr.json for the ADR explainer video.

Usage: make_adr_data.py <adr.md> <out-adr.json>
Env:   ANTHROPIC_API_KEY

One Sonnet call produces a single continuous spoken narration (Seth's
first-person register, ElevenLabs v3 audio tags) plus the on-screen data:
situation bullets, decision before/after comparisons, tradeoff bullets, and
a status line. Anchor phrases mark where each scene starts; the renderer
aligns cuts to them via whisper word timestamps. Retries on validation
failures (non-verbatim anchors), malformed JSON, transient API errors, and
a blown word budget.
"""
import json
import os
import re
import sys
import urllib.request

md_path, out_path = sys.argv[1], sys.argv[2]
md = open(md_path).read()

m = re.match(r"#\s*ADR[- ](\d+):\s*(.+)", md.splitlines()[0])
assert m, f"no ADR title in first line of {md_path}"
ADR_ID, TITLE = f"ADR-{m.group(1)}", m.group(2).strip()

# Status line for the closing card: first sentence of the **Status:** field.
sm = re.search(r"\*\*Status:\*\*\s*(.+)", md)
STATUS = re.sub(r"[*_`]", "", sm.group(1)).split(".")[0].strip() if sm else "Documented"

EXEMPLAR = (
    "[warm] Hey, quick MembersIntel update for the week of July seventh. So we merged ten "
    "pull requests this week, a hundred and twenty-six commits underneath them, and three of "
    "those are the ones I'd actually tell you about over coffee. The content taxonomy picked "
    "up platform and question-type facets, which means retrieval keeps getting sharper. The "
    "playbook corpus went through a full de-identification sweep and came out clean... "
    "[relieved] which was honestly a relief. [casually] Couple of smaller ones while I have "
    "you: we closed a register-tier bypass, and playbook batch five went live in the global "
    "brain. [warm] Ping me if you want the detail on any of it."
)

PROMPT = f"""You write the narration for a ~60-second video explaining one architecture
decision record to the MembersIntel team, spoken by Seth (the lead architect who wrote it).
The audience is teammates and the CEO — smart, busy, not all engineers. Source material:

<adr>
{md}
</adr>

Length budget (spoken at ~155 wpm): the narration must be UNDER 150 words, not counting
bracketed tags. Explain what the decision IS and WHY, in plain language — no section
headings read aloud, no jargon the CEO wouldn't know (translate it), never read file paths
or endpoint URLs aloud.

Write a JSON object with exactly these keys:
- "narration": ONE continuous spoken string (read in a single take). Flow: a one-line hook
  saying what this decision is about in plain words; then the situation that forced a
  decision; then the decision itself, walking each key point; then what it costs or trades
  away, honestly; then the current status, ending with a casual sign-off. Weave in 3-5
  ElevenLabs v3 audio tags in square brackets where delivery should shift — e.g. [warm] on
  the hook and sign-off, [thoughtful] on the tradeoffs. Tags are delivery directions, never
  spoken words.
- "anchors": {{"situation","tradeoffs","wrap"}} — three VERBATIM excerpts of 3-4 consecutive
  words copied exactly from the narration (no bracketed tags inside them; use plain
  lowercase words — avoid numbers, hyphenated words, contractions, code identifiers, and compound words that are sometimes written as two words (like dataset or changelog),
  which speech-to-text transcribes differently). "situation" = where the forcing situation
  starts, "tradeoffs" = where the costs start, "wrap" = where the status/sign-off starts.
  They must occur in the narration in that order.
- "changes": array of 1-3 items, one per key point of the decision, in the order discussed.
  Each is {{"title","before","after","anchor"}}: "title" names the point (max 5 words);
  "before" and "after" describe what it moved from and to (max 5 words each); "anchor" is a
  VERBATIM 3-4 consecutive-word excerpt where that point's discussion begins (same rules).
  All change anchors must fall between the "situation" anchor and the "tradeoffs" anchor.
- "situation_bullets": array of 2-3 short strings (on-screen, max 9 words each) — the
  forces that made this decision necessary.
- "tradeoff_bullets": array of 1-3 short strings (max 9 words each) — what this costs.

Voice rules: conversational, contractions, first person, no headline fragments, no
bullet-speak. Numbers spoken as words where natural. Match the voice of this exemplar
(it's a weekly update — match its register, not its content):

{json.dumps(EXEMPLAR)}

Facts only from the ADR — do not invent details. Return ONLY the JSON object."""

CEILING = 150


def generate(prompt_text):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt_text}],
        }).encode(),
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    body = json.load(urllib.request.urlopen(req, timeout=120))
    text = "".join(b.get("text", "") for b in body["content"])
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError(f"model returned no JSON object; head: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def spoken_words(n):
    return len(re.sub(r"\[[^\]]+\]\s*", "", n).split())


def validate(d):
    if not isinstance(d.get("narration"), str) or not d["narration"].strip():
        raise ValueError("narration missing")
    if not isinstance(d.get("changes"), list) or not d["changes"]:
        raise ValueError("changes missing")
    for c in d["changes"]:
        for f in ("title", "before", "after", "anchor"):
            if not isinstance(c.get(f), str) or not c[f].strip():
                raise ValueError(f'change field "{f}" missing')
    plain = re.sub(r"\[[^\]]+\]\s*", "", d["narration"]).lower()
    sequence = ([("anchors.situation", (d.get("anchors") or {}).get("situation"))]
                + [(f"changes[{i}].anchor", c["anchor"]) for i, c in enumerate(d["changes"])]
                + [("anchors.tradeoffs", (d.get("anchors") or {}).get("tradeoffs")),
                   ("anchors.wrap", (d.get("anchors") or {}).get("wrap"))])
    pos = 0
    for name, a in sequence:
        if not isinstance(a, str) or not a.strip():
            raise ValueError(f"{name} missing")
        needle = re.sub(r"\[[^\]]+\]\s*", "", a).lower()
        i = plain.find(needle, pos)
        if i == -1:
            raise ValueError(f'{name} ("{a}") not found verbatim (and in order) in narration')
        pos = i + len(needle)
    for key, lo, hi in (("situation_bullets", 2, 3), ("tradeoff_bullets", 1, 3)):
        v = d.get(key)
        if not isinstance(v, list) or not (lo <= len(v) <= hi):
            raise ValueError(f"{key} must be {lo}-{hi} strings")


data = None
feedback = ""
for attempt in range(1, 5):
    try:
        candidate = generate(PROMPT + feedback)
        validate(candidate)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"attempt {attempt} failed: {str(e)[:200]}")
        if isinstance(e, json.JSONDecodeError):
            feedback = ("\n\nYour previous reply was not parseable JSON. Return ONLY one valid "
                        "JSON object, with double quotes inside string values escaped.")
        else:
            feedback = (f"\n\nYour previous attempt was rejected: {e}. Every anchor must be 3-4 "
                        "CONSECUTIVE words copied character-for-character from your final "
                        "narration text (re-check each one against the narration before "
                        "answering), with change anchors between the situation and tradeoffs "
                        "anchors, all in discussion order.")
        continue
    except Exception as e:  # transient API errors retry with the same prompt
        print(f"attempt {attempt} failed: {str(e)[:200]}")
        continue
    data = candidate
    words = spoken_words(candidate["narration"])
    if words > CEILING * 1.25 and attempt < 4:
        print(f"narration {words} words > {CEILING}-word budget; retrying")
        feedback = (f"\n\nYour previous draft was {words} spoken words — the ceiling is "
                    f"{CEILING}. Cut whole items rather than compressing sentences; anything "
                    "dropped from the narration can still appear in the on-screen lists.")
        continue
    break
assert data, "no draft passed validation after 4 attempts"

adr = {
    "adr_id": ADR_ID,
    "title": TITLE,
    "status_line": STATUS,
    "narration": data["narration"],
    "anchors": data["anchors"],
    "changes": data["changes"],
    "situation_bullets": data["situation_bullets"],
    "tradeoff_bullets": data["tradeoff_bullets"],
    "output": f"adr-{ADR_ID.split('-')[1]}",
}
json.dump(adr, open(out_path, "w"), indent=2, ensure_ascii=False)
print(f"adr.json written: {adr['output']} — {TITLE} ({spoken_words(data['narration'])} words)")
