#!/usr/bin/env bash
# city_voice.sh <story-name> <work-dir-name> "<pause list, comma separated>"
# Voice for one city video: sync the story's lines from <story>.vo.json (and set the pauses), generate three takes per line,
# re-pick the smoothest takes, speech-check (re-picks a take that says something different), then take real word onsets.
set -euo pipefail
name=$1; dir=$HOME/work/$2; pauses=$3
here=$(cd "$(dirname "$0")" && pwd); cd "$here"
PY=$HOME/projects/memberpress-ai-cast/.venv/bin/python
/usr/bin/python3 - "$name" "$pauses" <<'PYE'
import json, sys
name, pauses = sys.argv[1], [float(x) if x else None for x in sys.argv[2].split(",")]
v = json.load(open(f"stories/{name}.vo.json")); d = json.load(open(f"stories/{name}.json"))
vm = {x["id"]: x for x in v["shots"]}
for b, p in zip(d["beats"], pauses + [None] * 20):
    b["vo"] = vm["s" + b["id"][1:]]["vo"]
    if p is not None:
        b["pause"] = p
json.dump(d, open(f"stories/{name}.json", "w"), indent=1)
PYE
set -a; source ~/.config/dev-secrets/secrets.env; set +a
/usr/bin/python3 gen_vo.py "stories/$name.vo.json" "$dir/vo" > /dev/null 2>&1
/usr/bin/python3 pick_smooth.py "$dir/vo" > /dev/null
$PY stt_check.py "$name" "$2" --fix 2>&1 | grep -v MKL | grep -E "MISMATCH|^$name"
$PY whisper_words.py "$dir/vo" 2>&1 | grep -c matched
