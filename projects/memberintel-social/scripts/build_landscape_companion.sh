#!/usr/bin/env bash
# Render a landscape (1920x1080) companion for a portrait episode, for
# desktop blog/site embeds. Portrait stays the canonical <slug>.mp4; this
# writes <slug>-landscape.mp4 alongside it — same audio takes (TTS cache is
# keyed by episode identity, not aspect), no re-recording.
#
# Usage: build_landscape_companion.sh <episode.json>
set -euo pipefail
cd "/Users/sethshoultes/Local Sites/OpenMontage"
set -a; source ~/.config/dev-secrets/secrets.env; set +a
.venv/bin/python projects/memberintel-social/scripts/build_short.py "$1" youtube_landscape
