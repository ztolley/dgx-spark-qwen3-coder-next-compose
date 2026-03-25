#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
TASK_PATH = ROOT_DIR / "evals" / "coding_tasks.json"
RESULT_DIR = ROOT_DIR / ".results"


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip() + "\n"
    return text.strip() + "\n"


def decode_escaped_text(text: str) -> str:
    return text.encode("utf-8").decode("unicode_escape")


def load_tasks(task_ids: set[str] | None) -> list[dict]:
    tasks = json.loads(TASK_PATH.read_text())
    if not task_ids:
        return tasks
    return [task for task in tasks if task["id"] in task_ids]


def run_task(base_url: str, model: str, task: dict, max_tokens: int) -> dict:
    prompt = (
        "You are being evaluated for coding correctness. "
        "Follow the user's formatting instruction exactly.\n\n"
        + decode_escaped_text(task["prompt"])
    )
    start = time.perf_counter()
    response = post_json(
        base_url.rstrip("/") + "/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        },
    )
    elapsed = time.perf_counter() - start

    text = response["choices"][0]["message"]["content"]
    code = extract_code(text)

    with tempfile.TemporaryDirectory(prefix=f"quality-eval-{task['id']}-") as td:
        temp_dir = Path(td)
        candidate_path = temp_dir / "candidate.py"
        runner_path = temp_dir / "test_runner.py"
        candidate_path.write_text(code)
        runner_path.write_text(decode_escaped_text(task["test_code"]))
        proc = subprocess.run(
            [sys.executable, str(runner_path)],
            cwd=temp_dir,
            capture_output=True,
            text=True,
        )

    usage = response.get("usage") or {}
    return {
        "task_id": task["id"],
        "description": task["description"],
        "passed": proc.returncode == 0,
        "latency_seconds": elapsed,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "response_text": text,
        "candidate_code": code,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run small coding-quality checks against an OpenAI-compatible endpoint.")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:30000/v1"))
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("MAX_TOKENS", "1024")))
    parser.add_argument("--task", action="append", dest="tasks", help="Task id to run. Can be passed multiple times.")
    parser.add_argument("--output", default=os.environ.get("OUTPUT", str(RESULT_DIR / "quality-eval.json")))
    args = parser.parse_args()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    model = args.model
    if not model:
        model = get_json(args.base_url.rstrip("/") + "/models")["data"][0]["id"]

    tasks = load_tasks(set(args.tasks) if args.tasks else None)
    if not tasks:
        print("No tasks selected.", file=sys.stderr)
        return 1

    results = [run_task(args.base_url, model, task, args.max_tokens) for task in tasks]
    passed = sum(1 for result in results if result["passed"])
    summary = {
        "base_url": args.base_url,
        "model": model,
        "task_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }

    Path(args.output).write_text(json.dumps(summary, indent=2))

    print(f"Model: {model}")
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['task_id']}: {result['latency_seconds']:.2f}s")
        if not result["passed"] and result["stderr"]:
            print(result["stderr"].strip())
    print(f"Summary: {passed}/{len(results)} passed")
    print(f"Saved {args.output}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
