#!/usr/bin/env bash
# Hands-off wrapper for running a v2 collection session.
# Suitable for SSHing into Laptop 1, kicking this off in tmux, and walking away.
#
# Usage:
#   bash data_collection_v2/scripts/run_session.sh smoke
#   bash data_collection_v2/scripts/run_session.sh keystone_1500
#   bash data_collection_v2/scripts/run_session.sh keystone_laptop1

set -euo pipefail

PRESET="${1:-smoke}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
CONFIG="$REPO_ROOT/data_collection_v2/configs/${PRESET}.yaml"

if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: config not found: $CONFIG"
  echo "Available presets:"
  ls "$REPO_ROOT/data_collection_v2/configs/" | sed 's/\.yaml$//' | sed 's/^/  /'
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M)"
OUTPUT_DIR="${AIC_V2_OUTPUT_DIR_BASE:-/data/aic_v2}/run_${PRESET}_${STAMP}"

echo "==> v2 session: preset=$PRESET output=$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

cd "$REPO_ROOT"
exec pixi run python -m data_collection_v2.cli session \
    --config "$CONFIG" \
    --output "$OUTPUT_DIR"
