#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULT_DIR="${ROOT_DIR}/.results"
mkdir -p "${RESULT_DIR}"

BASE_URL="${BASE_URL:-http://127.0.0.1:30000/v1}"
PROMPT_TOKENS="${PROMPT_TOKENS:-2048}"
RESPONSE_TOKENS="${RESPONSE_TOKENS:-128}"
RUNS="${RUNS:-1}"
DEPTHS="${DEPTHS:-0 24576}"
CONCURRENCY="${CONCURRENCY:-1}"
LATENCY_MODE="${LATENCY_MODE:-generation}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-${RESULT_DIR}/llama-benchy-main}"

if [[ -n "${MODEL:-}" ]]; then
  DETECTED_MODEL="${MODEL}"
else
  DETECTED_MODEL="$(
    python3 - <<'PY' "${BASE_URL}"
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
with urllib.request.urlopen(base_url + "/models", timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))
print(data["data"][0]["id"])
PY
  )"
fi

if [[ -n "${LLAMA_BENCHY_CMD:-}" ]]; then
  BENCH_CMD=("${LLAMA_BENCHY_CMD}")
elif command -v llama-benchy >/dev/null 2>&1; then
  BENCH_CMD=("llama-benchy")
elif command -v uvx >/dev/null 2>&1; then
  BENCH_CMD=("uvx" "llama-benchy")
else
  printf '%s\n' "Unable to find llama-benchy. Set LLAMA_BENCHY_CMD, install llama-benchy, or install uvx." >&2
  exit 1
fi

printf 'Benchmarking %s via %s\n' "${DETECTED_MODEL}" "${BASE_URL}"
printf 'Depths: %s | Runs: %s | Concurrency: %s\n' "${DEPTHS}" "${RUNS}" "${CONCURRENCY}"

"${BENCH_CMD[@]}" \
  --base-url "${BASE_URL}" \
  --model "${DETECTED_MODEL}" \
  --pp "${PROMPT_TOKENS}" \
  --tg "${RESPONSE_TOKENS}" \
  --depth ${DEPTHS} \
  --runs "${RUNS}" \
  --concurrency "${CONCURRENCY}" \
  --latency-mode "${LATENCY_MODE}" \
  --enable-prefix-caching \
  --save-result "${OUTPUT_PREFIX}.json" \
  --format json

printf 'Saved %s\n' "${OUTPUT_PREFIX}.json"
