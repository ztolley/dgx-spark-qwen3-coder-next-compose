#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_PACKAGES="/usr/local/lib/python3.12/dist-packages"

echo "Patching Qwen3-Coder-Next crashing on start"
if patch --dry-run --silent --batch -N -p1 -d "${SITE_PACKAGES}" < "${SCRIPT_DIR}/fix_crash.diff" >/dev/null 2>&1; then
  patch --silent --batch -N -p1 -d "${SITE_PACKAGES}" < "${SCRIPT_DIR}/fix_crash.diff"
else
  echo "Crash patch already present or no longer needed, skipping"
fi

echo "Reverting PR #34279 that causes slowness"
if patch --dry-run --silent --batch -N -R -p1 -d "${SITE_PACKAGES}" < "${SCRIPT_DIR}/fix_slowness.diff" >/dev/null 2>&1; then
  patch --silent --batch -N -R -p1 -d "${SITE_PACKAGES}" < "${SCRIPT_DIR}/fix_slowness.diff"
else
  echo "Slowness patch already reverted or no longer needed, skipping"
fi

echo "Fixing Triton allocator bug"
cp "${SCRIPT_DIR}"/_triton* "${SITE_PACKAGES}/"
