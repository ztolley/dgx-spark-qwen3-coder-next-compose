#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

python3 - <<'PY'
import json
import sys
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
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = resp.read()
    elapsed = time.perf_counter() - start
    data = json.loads(body.decode("utf-8"))
    data["_elapsed_seconds"] = elapsed
    return data


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


main_models = get_json("http://127.0.0.1:30000/v1/models")
auto_models = get_json("http://127.0.0.1:30001/v1/models")

main_model = main_models["data"][0]["id"]
auto_model = auto_models["data"][0]["id"]
print(f"Main model: {main_model}")
print(f"Autocomplete model: {auto_model}")

main_reply = post_json(
    "http://127.0.0.1:30000/v1/chat/completions",
    {
        "model": main_model,
        "messages": [
            {
                "role": "user",
                "content": "Return only the string OK.",
            }
        ],
        "temperature": 0,
        "max_tokens": 8,
    },
)
main_text = main_reply["choices"][0]["message"]["content"].strip()
print(f"Main response: {main_text!r} in {main_reply['_elapsed_seconds']:.2f}s")

auto_reply = post_json(
    "http://127.0.0.1:30001/v1/completions",
    {
        "model": auto_model,
        "prompt": "def add(a, b):\n    ",
        "temperature": 0,
        "max_tokens": 32,
    },
)
auto_text = auto_reply["choices"][0]["text"]
print(f"Autocomplete response: {auto_text!r} in {auto_reply['_elapsed_seconds']:.2f}s")

if main_text != "OK":
    print("Unexpected main model response", file=sys.stderr)
    sys.exit(1)

if not auto_text.strip():
    print("Autocomplete returned empty output", file=sys.stderr)
    sys.exit(1)
PY
