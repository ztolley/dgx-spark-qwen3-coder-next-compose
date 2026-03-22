#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULT_DIR="${ROOT_DIR}/.results"
mkdir -p "${RESULT_DIR}"

python3 - <<'PY' > "${RESULT_DIR}/bench.json"
import json
import time
import urllib.request


def post_json(url: str, payload: dict) -> dict:
    start = time.perf_counter()
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = resp.read()
    elapsed = time.perf_counter() - start
    data = json.loads(body.decode("utf-8"))
    return {"elapsed_seconds": elapsed, "response": data}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


main_model = get_json("http://127.0.0.1:30000/v1/models")["data"][0]["id"]
auto_model = get_json("http://127.0.0.1:30001/v1/models")["data"][0]["id"]
long_prefix = "\n".join(
    [f"line_{i} = {i}" for i in range(1200)]
) + "\n\nExplain in 3 sentences what this file pattern suggests.\n"

bench = {
    "main_model": main_model,
    "tests": [],
}

bench["tests"].append(
    {
        "name": "main_coldish_prompt",
        **post_json(
            "http://127.0.0.1:30000/v1/chat/completions",
            {
                "model": main_model,
                "messages": [{"role": "user", "content": long_prefix}],
                "temperature": 0,
                "max_tokens": 96,
            },
        ),
    }
)

bench["tests"].append(
    {
        "name": "main_prefix_cache_repeat",
        **post_json(
            "http://127.0.0.1:30000/v1/chat/completions",
            {
                "model": main_model,
                "messages": [{"role": "user", "content": long_prefix}],
                "temperature": 0,
                "max_tokens": 96,
            },
        ),
    }
)

bench["tests"].append(
    {
        "name": "autocomplete_short_completion",
        **post_json(
            "http://127.0.0.1:30001/v1/completions",
            {
                "model": auto_model,
                "prompt": "def fibonacci(n):\n    ",
                "temperature": 0,
                "max_tokens": 48,
            },
        ),
    }
)

print(json.dumps(bench, indent=2))
PY

printf '%s\n' '--- Bench summary ---'
python3 - <<'PY'
import json
from pathlib import Path

bench = json.loads(Path(".results/bench.json").read_text())
for test in bench["tests"]:
    print(f"{test['name']}: {test['elapsed_seconds']:.2f}s")
PY

printf '\n%s\n' '--- GPU processes ---'
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader || true

printf '\n%s\n' '--- Host memory ---'
free -h || true
