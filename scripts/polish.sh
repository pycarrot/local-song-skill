#!/usr/bin/env bash
# Make a hazy AI vocal sound crisp and upfront, then master.
# Splits vocals from the backing track, strips reverb wash from the vocal, adds presence/air,
# carves a pocket in the backing track and remixes at -14 LUFS.
# Usage: polish.sh <song.mp3|wav> <out.mp3> [fade_out_start_seconds] [vocal_boost_db]
set -euo pipefail
in=$1 out=$2 fade=${3:-} boost=${4:-1.5}
LS_HOME=${LS_HOME:-$HOME/.local-song}
SEP=${SEP_BIN:-$LS_HOME/venv/bin/audio-separator}
MODELS=${SEP_MODELS:-$LS_HOME/sep-models}
work=$(mktemp -d "${TMPDIR:-/tmp}/polish.XXXXXX")
trap 'rm -rf "$work"' EXIT

sep() { "$SEP" "$1" -m "$2" --model_file_dir "$MODELS" --output_dir "$work" --output_format WAV \
          --custom_output_names "$3" >"$work/sep.log" 2>&1 || { tail -20 "$work/sep.log"; exit 1; }; }
lufs() { ffmpeg -hide_banner -nostats -i "$1" -af ebur128 -f null - 2>&1 | awk '/^ +I:/{v=$2} END{print v}'; }

echo "1/4 separating vocals"
sep "$in" vocals_mel_band_roformer.ckpt '{"Vocals":"vox","Other":"inst"}'
echo "2/4 removing reverb from vocals"
sep "$work/vox.wav" UVR-DeEcho-DeReverb.pth '{"No Reverb":"dry","Reverb":"wet"}'

echo "3/4 shaping vocal"
# mud cut, presence + air, de-ess, gentle compression, a touch of harmonic excitement; keep 30% of the room
ffmpeg -v error -y -i "$work/dry.wav" -i "$work/wet.wav" -filter_complex \
  "[0]highpass=f=90,equalizer=f=250:t=q:w=1:g=-3,equalizer=f=3200:t=q:w=1.2:g=3,highshelf=f=9000:g=2.5,\
deesser=i=0.5,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,aexciter=amount=0.8:drive=6:freq=4000[d];\
[1]volume=0.3[w];[d][w]amix=inputs=2:normalize=0" "$work/vshaped.wav"
# put the shaped vocal back at its original level + boost dB, so the balance only moves on purpose
gain=$(awk -v a="$(lufs "$work/vox.wav")" -v b="$(lufs "$work/vshaped.wav")" -v c="$boost" 'BEGIN{print a-b+c}')

echo "4/4 remixing + mastering (vocal ${boost} dB louder)"
ffmpeg -v error -y -i "$work/vshaped.wav" -i "$work/inst.wav" -filter_complex \
  "[0]volume=${gain}dB[v];[1]equalizer=f=3000:t=q:w=0.8:g=-2[i];[v][i]amix=inputs=2:normalize=0" "$work/mix.wav"
# two-pass loudnorm: measure first, then normalise linearly to exactly -14 LUFS
m=$(ffmpeg -hide_banner -nostats -i "$work/mix.wav" -af loudnorm=I=-14:TP=-1:LRA=9:print_format=json -f null - 2>&1 |
    awk -F'"' '/input_i/{i=$4}/input_tp/{t=$4}/input_lra/{l=$4}/input_thresh/{h=$4}/target_offset/{o=$4}
      END{printf "measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s",i,t,l,h,o}')
ffmpeg -v error -y -i "$work/mix.wav" -af "loudnorm=I=-14:TP=-1:LRA=9:$m:linear=true${fade:+,afade=t=out:st=$fade:d=6}" \
  -ar 44100 -b:a 320k "$out"
echo "done: $out ($(lufs "$out") LUFS)"
