#!/usr/bin/env bash
# Idempotently disable global illumination in aic.sdf for headless throughput.
# Per context/11_24h_strategy/01_data_24h.md:97 — GI off gives ~+30% RTF.
#
# Safe to run multiple times. Writes a .bak alongside the original on first edit.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# aic_description is the package that owns the world SDF.
SDF_CANDIDATES=(
  "$REPO_ROOT/aic_description/worlds/aic.sdf"
  "$REPO_ROOT/aic_description/world/aic.sdf"
  "$REPO_ROOT/aic_description/models/aic_world/aic.sdf"
)

SDF=""
for cand in "${SDF_CANDIDATES[@]}"; do
  if [[ -f "$cand" ]]; then
    SDF="$cand"
    break
  fi
done

if [[ -z "$SDF" ]]; then
  # Last-ditch search.
  SDF="$(find "$REPO_ROOT/aic_description" -name 'aic.sdf' -type f 2>/dev/null | head -n1 || true)"
fi

if [[ -z "$SDF" ]]; then
  echo "ERROR: aic.sdf not found under $REPO_ROOT/aic_description"
  exit 1
fi

echo "Patching $SDF for GI off..."

# Look for either <global_illumination> or a <vsm><enabled>true</enabled></vsm>
# style tag. If we find a <global_illumination> block, set its <enabled> to false.
# If we find no GI block at all, we don't add one (the engine's default is fine).
if grep -q '<global_illumination>' "$SDF"; then
  # Make a backup once.
  if [[ ! -f "$SDF.bak" ]]; then
    cp "$SDF" "$SDF.bak"
  fi
  # Toggle <enabled>true</enabled> inside <global_illumination>...</global_illumination>
  # to <enabled>false</enabled> — idempotent because if it's already false it stays false.
  python3 - "$SDF" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path) as f:
    text = f.read()

def patch_block(text: str, tag: str) -> str:
    pattern = re.compile(
        rf'(<{tag}>.*?<enabled>)\s*true\s*(</enabled>.*?</{tag}>)',
        re.DOTALL,
    )
    return pattern.sub(r'\1false\2', text)

new = patch_block(text, "global_illumination")
new = patch_block(new, "vsm")

if new != text:
    with open(path, "w") as f:
        f.write(new)
    print("  -> patched.")
else:
    print("  -> already off (no change).")
PY
else
  echo "  -> no <global_illumination> block found; nothing to do."
fi
