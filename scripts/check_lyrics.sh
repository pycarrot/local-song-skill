#!/usr/bin/env bash
# Transcribe a take so the sung words can be compared with the lyrics (you cannot listen; this is how you check).
# Writes <audio>.whisper.json (word timings, used by w2lines.py) and prints timestamped lines.
# Usage: [WHISPER_MODEL=path.bin] check_lyrics.sh <audio> [lang]   lang = en, th, ja, … (default auto)
# Note: lines repeated at the very end are usually Whisper hallucinating over the outro, not the song.
set -euo pipefail
LS_HOME=${LS_HOME:-$HOME/.local-song}
in=$1 lang=${2:-auto}
model=${WHISPER_MODEL:-$LS_HOME/whisper/ggml-small.bin}
[ -f "$model" ] || { echo "whisper model not found: $model" >&2; exit 1; }
base=$(mktemp "${TMPDIR:-/tmp}/cl.XXXXXX"); tmp=$base.wav; trap 'rm -f "$base" "$tmp" "$base.log"' EXIT
ffmpeg -v error -y -i "$in" -ar 16000 -ac 1 "$tmp"
# DTW gives real per-word timings (t_dtw) for the karaoke video; it needs flash attention off. Preset: ggml-large-v3-turbo-q5_0.bin -> large.v3.turbo
dtw=$(basename "$model" .bin); dtw=${dtw#ggml-}; dtw=${dtw%-q[0-9]_[0-9]}; dtw=${dtw//-/.}
case $(whisper-cli --help 2>&1) in *--no-flash-attn*) nfa=-nfa;; *) nfa=;; esac  # 1.7 and older: no -nfa (FA already off), and unknown flags still exit 0
case $dtw in tiny|tiny.en|base|base.en|small|small.en|medium|medium.en|large.v1|large.v2|large.v3|large.v3.turbo) dtw="$nfa -dtw $dtw";; *) dtw="";; esac  # unknown model name: no DTW
rm -f "$in.whisper.json"  # never leave an older transcript to be mistaken for this one
# -mc 0: no previous text as context, which stops repeat loops over unclear vocals (same scores on clear English songs)
whisper-cli -m "$model" -f "$tmp" -l "$lang" -mc 0 -ojf -of "$in.whisper" -np $dtw >/dev/null 2>"$base.log" || { cat "$base.log" >&2; exit 1; }
[ -s "$in.whisper.json" ] || { echo "whisper-cli wrote no transcript:" >&2; cat "$base.log" >&2; exit 1; }
python3 -c "
import json, sys
for s in json.load(open(sys.argv[1], errors='replace'))['transcription']: print(s['timestamps']['from'][:8], s['text'].strip())" "$in.whisper.json"
