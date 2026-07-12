"""Turn a report markdown into report.json for the report explainer video.

Usage: make_report_data.py <report.md> <out-report.json> <output-slug>
Env:   ANTHROPIC_API_KEY

Same single-take tagged narration + whisper-anchor grammar as the ADR and
weekly templates, sized for a ~2-minute data-report walkthrough: KPI grid
for the headline numbers, comparison cards for the contrast findings,
highlights, and a takeaway.
"""
import json
import os
import re
import sys
import urllib.request

md_path, out_path, slug = sys.argv[1], sys.argv[2], sys.argv[3]
md = open(md_path).read()
TITLE = md.splitlines()[0].lstrip("# ").strip()

EXEMPLAR = (
    "[warm] Hey, quick MembersIntel update for the week of July seventh. So we merged ten "
    "pull requests this week, a hundred and twenty-six commits underneath them, and three of "
    "those are the ones I'd actually tell you about over coffee. The content taxonomy picked "
    "up platform and question-type facets, which means retrieval keeps getting sharper. "
    "[relieved] The playbook corpus came out clean, which was honestly a relief. [casually] "
    "Couple of smaller ones while I have you: we closed a register-tier bypass, and playbook "
    "batch five went live in the global brain. [warm] Ping me if you want the detail on any of it."
)

PROMPT = f"""You write the narration for a ~2-minute video presenting a data report, spoken
by Seth (the lead) — the report analyzes what separates membership businesses that grow from
ones that plateau. The audience is the team, the CEO, and potentially customers — smart,
busy, not analysts. Source material:

<report>
{md}
</report>

Length budget (spoken at ~155 wpm): the narration must be UNDER 280 words, not counting
bracketed tags. Lead with the findings that would change what a listener DOES — don't
inventory the report. Numbers spoken as words where natural.

Write a JSON object with exactly these keys:
- "narration": ONE continuous spoken string (read in a single take). Flow: a one-line hook
  about what the data says; then the headline numbers; then the two or three findings that
  actually matter, one at a time, each as a contrast (what people assume vs what the data
  shows, or what winners do vs what plateaued sites do); then one or two smaller findings
  worth knowing; then the single takeaway, ending with a casual sign-off. Weave in 4-6
  ElevenLabs v3 audio tags in square brackets where delivery should shift — e.g. [warm] on
  the hook and sign-off, [thoughtful] on a surprising finding. Tags are delivery directions,
  never spoken words.
- "anchors": {{"kpis","highlights","wrap"}} — three VERBATIM excerpts of 3-4 consecutive
  words copied exactly from the narration (no bracketed tags inside; use plain lowercase
  words — avoid numbers, hyphenated words, contractions, symbols, and compound words that are sometimes written as two words (like dataset or changelog), which speech-to-text
  transcribes differently). "kpis" = where the headline numbers start, "highlights" = where
  the smaller findings start, "wrap" = where the takeaway starts. In narration order.
- "changes": array of 2-4 items, one per major finding, in the order discussed. Each is
  {{"title","before","after","anchor"}}: "title" names the finding (max 5 words); "before"
  and "after" are the contrast (max 5 words each, e.g. "free membership tiers" → "free
  tools that sell"); "anchor" is a VERBATIM 3-4 consecutive-word excerpt where that
  finding's discussion begins (same rules). All change anchors fall between the "kpis"
  anchor and the "highlights" anchor.
- "kpis": array of 2-4 {{"label","value"}} with REAL numbers from the report (value must be
  a plain number — use 750 with label "median site revenue ($K/yr)" style units in the
  label, never strings like "$750K").
- "highlights": array of 2-3 short strings (on-screen bullets, max 9 words each).
- "takeaway": one short string (max 12 words) — the closing card.

Voice rules: conversational, contractions, first person, no headline fragments, no
bullet-speak. Match the voice of this exemplar (a weekly update — match register, not
content):

{json.dumps(EXEMPLAR)}

Facts only from the report — do not invent numbers. Return ONLY the JSON object."""

CEILING = 280


def generate(prompt_text):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 2000,
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
    if not isinstance(d.get("changes"), list) or len(d["changes"]) < 2:
        raise ValueError("changes must have at least 2 findings")
    for c in d["changes"]:
        for f in ("title", "before", "after", "anchor"):
            if not isinstance(c.get(f), str) or not c[f].strip():
                raise ValueError(f'change field "{f}" missing')
    plain = re.sub(r"\[[^\]]+\]\s*", "", d["narration"]).lower()
    sequence = ([("anchors.kpis", (d.get("anchors") or {}).get("kpis"))]
                + [(f"changes[{i}].anchor", c["anchor"]) for i, c in enumerate(d["changes"])]
                + [("anchors.highlights", (d.get("anchors") or {}).get("highlights")),
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
    if not isinstance(d.get("kpis"), list) or len(d["kpis"]) < 2:
        raise ValueError("kpis missing")
    for k in d["kpis"]:
        if not isinstance(k.get("label"), str) or not k["label"]:
            raise ValueError("kpi label missing")
        if k.get("value") is None or (isinstance(k["value"], str) and not k["value"].strip()):
            raise ValueError(f'kpi "{k["label"]}" value missing')
        k["value"] = float(k["value"])
        if k["value"] != k["value"]:  # NaN
            raise ValueError(f'kpi "{k["label"]}" value is not a number')
    if not isinstance(d.get("highlights"), list) or not (2 <= len(d["highlights"]) <= 3):
        raise ValueError("highlights must be 2-3 strings")
    if not isinstance(d.get("takeaway"), str) or not d["takeaway"].strip():
        raise ValueError("takeaway missing")


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
                        "answering), all in discussion order.")
        continue
    except Exception as e:
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

report = {
    "title": TITLE,
    "narration": data["narration"],
    "anchors": data["anchors"],
    "changes": data["changes"],
    "kpis": data["kpis"],
    "highlights": data["highlights"],
    "takeaway": data["takeaway"],
    "output": slug,
}
json.dump(report, open(out_path, "w"), indent=2, ensure_ascii=False)
print(f"report.json written: {slug} — {TITLE} ({spoken_words(data['narration'])} words)")
