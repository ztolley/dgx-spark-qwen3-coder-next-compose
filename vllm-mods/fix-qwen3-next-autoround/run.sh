#!/usr/bin/env bash
set -euo pipefail

SITE_PACKAGES="/usr/local/lib/python3.12/dist-packages"

echo "Reverting PR #35156 for Qwen3 AutoRound"
if curl -L https://patch-diff.githubusercontent.com/raw/vllm-project/vllm/pull/35156.diff | patch --batch -N -R -p1 -d "${SITE_PACKAGES}"; then
  echo "AutoRound patch reverted"
else
  echo "AutoRound patch already reverted or no longer needed, skipping"
fi
