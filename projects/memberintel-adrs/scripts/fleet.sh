#!/usr/bin/env bash
# Render an ADR explainer for every ADR that doesn't have one yet.
# Resumable: skips ADRs whose render already exists. Failure-isolated:
# one bad ADR is logged and skipped, the batch continues.
# Usage: fleet.sh [adr-docs-dir]
set -uo pipefail
cd "$(dirname "$0")/../../.."
set -a; source ~/.config/dev-secrets/secrets.env; set +a
ADR_DIR="${1:-/Users/sethshoultes/Local Sites/memberintel/docs/adr}"
P="projects/memberintel-adrs"

for MD in "$ADR_DIR"/[0-9]*.md; do
  NUM="$(basename "$MD" | cut -d- -f1)"
  OUT="$P/renders/adr-${NUM}.mp4"
  if [ -s "$OUT" ]; then
    echo "SKIP adr-${NUM} (already rendered)"
    continue
  fi
  echo "=== adr-${NUM}: $(basename "$MD") ==="
  if ! .venv/bin/python "$P/scripts/make_adr_data.py" "$MD" "$P/adr-${NUM}.json"; then
    echo "FAILED adr-${NUM}: data-gen"; continue
  fi
  if ! .venv/bin/python "$P/scripts/build_adr.py" "$P/adr-${NUM}.json"; then
    echo "FAILED adr-${NUM}: render"; continue
  fi
  echo "DONE adr-${NUM}"
done
echo "=== ADR FLEET COMPLETE ==="
ls -lh "$P/renders/" | grep adr- | wc -l
