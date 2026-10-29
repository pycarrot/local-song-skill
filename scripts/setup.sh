#!/usr/bin/env bash
# One-time install of everything the skill needs, into $LS_HOME (default ~/.local-song).
# Usage: setup.sh [hq|fast]   hq = SFT DiT, 50 steps (cleaner vocals, slower) · fast = turbo DiT, 8 steps
set -euo pipefail
quality=${1:-hq}
LS_HOME=${LS_HOME:-$HOME/.local-song}
ACESTEP_REF=${ACESTEP_REF:-de858d8}   # last tested acestep.cpp commit
LM=${LM:-0.6B}                        # 0.6B | 1.7B (better lyrics/structure, +1.1 GB)
HF=https://huggingface.co/Serveurperso/ACE-Step-1.5-GGUF/resolve/main
case $quality in hq) dit=acestep-v15-sft-Q8_0.gguf ;; fast) dit=acestep-v15-turbo-Q8_0.gguf ;;
  *) echo "usage: setup.sh [hq|fast]"; exit 1 ;; esac

mkdir -p "$LS_HOME"
free_gb=$(df -Pk "$LS_HOME" | awk 'NR==2{printf "%d", $4/1048576}')
if [ "$free_gb" -lt 7 ] && [ -z "${FORCE:-}" ]; then
  echo "Need about 7 GB free (models 4.4 + tools 1.5 + separation models 1.1); only ${free_gb} GB free."
  echo "Free some space or re-run with FORCE=1."; exit 1
fi

need=()
for c in git cmake ffmpeg uv whisper-cli; do command -v $c >/dev/null || need+=("$c"); done
if [ ${#need[@]} -gt 0 ]; then
  if command -v brew >/dev/null; then
    pk=("${need[@]/whisper-cli/whisper-cpp}"); echo "brew install ${pk[*]}"; brew install -q "${pk[@]}"
  else
    echo "Missing: ${need[*]}. Install them (whisper-cli comes from whisper.cpp), then re-run."; exit 1
  fi
fi

A=$LS_HOME/acestep.cpp
if [ ! -x "$A/build/ace-synth" ]; then
  [ -d "$A" ] || git clone --recurse-submodules https://github.com/ServeurpersoCom/acestep.cpp.git "$A"
  git -C "$A" checkout -q "$ACESTEP_REF" && git -C "$A" submodule update -q --init --recursive
  if [ "$(uname)" = Darwin ]; then flags="-DGGML_METAL=ON"
  elif command -v nvcc >/dev/null; then flags="-DGGML_CUDA=ON"
  else flags="-DGGML_BLAS=ON"; fi
  cmake -S "$A" -B "$A/build" $flags -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build "$A/build" --config Release -j"$(getconf _NPROCESSORS_ONLN)" 2>&1 | tail -1
fi

dl() { [ -s "$2/$1" ] || { echo "downloading $1"; mkdir -p "$2"; curl -L --fail -# -o "$2/$1.part" "$3/$1" && mv "$2/$1.part" "$2/$1"; }; }
for f in vae-BF16.gguf Qwen3-Embedding-0.6B-Q8_0.gguf "acestep-5Hz-lm-$LM-Q8_0.gguf" "$dit"; do dl "$f" "$A/models" "$HF"; done
dl ggml-small.bin "$LS_HOME/whisper" https://huggingface.co/ggerganov/whisper.cpp/resolve/main

if [ ! -x "$LS_HOME/venv/bin/audio-separator" ]; then
  uv venv -q -p 3.12 "$LS_HOME/venv"
  uv pip install -q -p "$LS_HOME/venv" "audio-separator[cpu]" audioread pillow numpy
fi
echo "ready: $LS_HOME (quality=$quality, LM=$LM)"
