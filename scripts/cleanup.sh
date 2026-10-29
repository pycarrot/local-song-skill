#!/usr/bin/env bash
# Free disk. Usage: cleanup.sh models   (drop the ~5.5 GB of models, keep built tools)
#                   cleanup.sh all      (remove $LS_HOME entirely)
set -euo pipefail
LS_HOME=${LS_HOME:-$HOME/.local-song}
case ${1:-} in
  models) rm -rf "$LS_HOME/acestep.cpp/models" "$LS_HOME/sep-models" "$LS_HOME/whisper" ;;
  all) rm -rf "$LS_HOME" ;;
  *) echo "usage: cleanup.sh models|all"; exit 1 ;;
esac
df -h "$HOME" | tail -1
