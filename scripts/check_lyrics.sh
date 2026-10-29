#!/usr/bin/env bash
# Transcribe a take so the sung words can be compared with the lyrics (you cannot listen; this is how you check).
# Writes <audio>.whisper.json (word timings, used by w2lines.py) and prints timestamped lines.
# Usage: check_lyrics.sh <audio> [lang]   lang = en, th, ja, … (default auto)
# Note: lines repeated at the very end are usually Whisper hallucinating over the outro, not the song.
set -euo pipefail
LS_HOME=${LS_HOME:-$HOME/.local-song}
in=$1 lang=${2:-auto}
tmp=$(mktemp "${TMPDIR:-/tmp}/cl.XXXXXX").wav; trap 'rm -f "$tmp"' EXIT
ffmpeg -v error -y -i "$in" -ar 16000 -ac 1 "$tmp"
whisper-cli -m "$LS_HOME/whisper/ggml-small.bin" -f "$tmp" -l "$lang" -ojf -of "$in.whisper" -np >/dev/null 2>&1
python3 -c "
import json, sys
for s in json.load(open(sys.argv[1]))['transcription']: print(s['timestamps']['from'][:8], s['text'].strip())" "$in.whisper.json"
