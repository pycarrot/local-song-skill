#!/usr/bin/env bash
# Compose + render takes from a request JSON. Writes <outdir>/req0.json, req1.json (audio codes) and req00.wav, req10.wav.
# Usage: generate.sh <request.json> <outdir>
# Re-render one take with other synth settings (same melody/structure): edit <outdir>/req1.json, then
#   generate.sh --synth-only <outdir>/req1.json
set -euo pipefail
LS_HOME=${LS_HOME:-$HOME/.local-song}
A=$LS_HOME/acestep.cpp
synth() { "$A/build/ace-synth" --models "$A/models" --request "$1" >"${1%.json}.synth.log" 2>&1 ||
            { tail -20 "${1%.json}.synth.log"; exit 1; }; }

if [ "$1" = --synth-only ]; then synth "$2"; ls "${2%.json}"0.*; exit; fi

req=$1 out=$2
mkdir -p "$out"
# defaults: whichever DiT is installed, lossless output
python3 - "$req" "$out/req.json" "$A/models" <<'EOF'
import json, os, sys
r = json.load(open(sys.argv[1])); models = os.listdir(sys.argv[3])
if "synth_model" not in r or r["synth_model"] not in models:
    sft = "acestep-v15-sft-Q8_0.gguf" in models
    r.update(synth_model="acestep-v15-sft-Q8_0.gguf" if sft else "acestep-v15-turbo-Q8_0.gguf",
             inference_steps=50 if sft else 8, guidance_scale=1.0, shift=1.0 if sft else 3.0)
if "lm_model" not in r or r["lm_model"] not in models:
    r["lm_model"] = sorted(m for m in models if m.startswith("acestep-5Hz-lm"))[-1]
r.setdefault("output_format", "wav24"); r.setdefault("lm_batch_size", 2)
json.dump(r, open(sys.argv[2], "w"), indent=1)
print("synth:", r["synth_model"], r["inference_steps"], "steps · lm:", r["lm_model"])
EOF
cd "$out"
echo "composing (LM)…"
"$A/build/ace-lm" --models "$A/models" --request req.json >lm.log 2>&1 || { tail -20 lm.log; exit 1; }
for r in req[0-9].json; do echo "rendering $r…"; synth "$r"; done
ls -1 "$PWD"/req[0-9]0.*
