#!/usr/bin/env bash
# render_page_video.sh <story-name> <work-dir-name> <out-name>
# Renders one page video from stories/<story-name>.json with the work dir's stills/ and vo/ (~/work/<work-dir-name>/), niced.
# The log goes to ~/work/<work-dir-name>/out/<out-name>.log; "OK" on its last line means it finished.
set -euo pipefail
story=$1; dir=$HOME/work/$2; out=$3
here=$(cd "$(dirname "$0")" && pwd)
s3=$HOME/work/seo-v3-media3
cd "$here"
nice /usr/bin/python3 build_story_video.py "stories/$story.json" "$dir/stills" "$dir/vo" "$dir/out/$out.mp4" \
  --music "$s3/music/bed.mp3" --sfx "$s3/sfx/whoosh1.mp3,$s3/sfx/whoosh2.mp3" > "$dir/out/$out.log" 2>&1
tail -1 "$dir/out/$out.log"
