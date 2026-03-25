#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK_DIR = Path("/tmp/polyglot-benchmark")
DEFAULT_OUTPUT = ROOT_DIR / ".results" / "aider-polyglot-python.json"
DEFAULT_TASK_LIST = ROOT_DIR / "evals" / "aider-polyglot-python-sample.txt"
BENCHMARK_REPO = "https://github.com/Aider-AI/polyglot-benchmark.git"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


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


def detect_model(base_url: str) -> str:
    return get_json(base_url.rstrip("/") + "/models")["data"][0]["id"]


def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip() + "\n"
    stripped = text.strip()
    if stripped.startswith("```python"):
        stripped = stripped[len("```python") :].lstrip()
    elif stripped.startswith("```"):
        stripped = stripped[3:].lstrip()
    return stripped + ("\n" if not stripped.endswith("\n") else "")


def ensure_benchmark_repo(repo_dir: Path) -> Path:
    if (repo_dir / ".git").exists():
        return repo_dir
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", BENCHMARK_REPO, str(repo_dir)])
    return repo_dir


def load_task_ids(task_list: Path | None, benchmark_root: Path, limit: int | None) -> list[str]:
    if task_list and task_list.exists():
        tasks = [line.strip() for line in task_list.read_text().splitlines() if line.strip()]
    else:
        tasks = sorted(path.name for path in benchmark_root.iterdir() if path.is_dir())
    if limit is not None:
        tasks = tasks[:limit]
    return tasks


def find_python_source_and_test(task_dir: Path) -> tuple[Path, Path]:
    py_files = sorted(path for path in task_dir.glob("*.py") if path.is_file())
    test_files = [path for path in py_files if path.stem.endswith("_test")]
    source_files = [path for path in py_files if path not in test_files]
    if len(source_files) != 1 or len(test_files) != 1:
        raise RuntimeError(f"Expected one Python source file and one test file in {task_dir}")
    return source_files[0], test_files[0]


def run_python_task(base_url: str, model: str, task_dir: Path, max_tokens: int) -> dict:
    source_path, test_path = find_python_source_and_test(task_dir)
    instructions = (task_dir / ".docs" / "instructions.md").read_text()
    source_text = source_path.read_text()

    prompt = (
        "You are being evaluated on a Python coding task.\n"
        "Implement the requested behavior in the starter file below.\n"
        "Return only the complete updated file in a single ```python``` block.\n"
        "Do not omit unchanged code. Do not add explanation.\n\n"
        f"{instructions}\n\n"
        f"File path: {source_path.name}\n\n"
        f"```python\n{source_text}\n```"
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
    candidate = extract_code(text)

    with tempfile.TemporaryDirectory(prefix=f"polyglot-{task_dir.name}-") as td:
        temp_dir = Path(td)
        work_dir = temp_dir / task_dir.name
        shutil.copytree(task_dir, work_dir)
        (work_dir / source_path.name).write_text(candidate)
        proc = subprocess.run(
            [sys.executable, str(work_dir / test_path.name)],
            cwd=work_dir,
            capture_output=True,
            text=True,
        )

    usage = response.get("usage") or {}
    return {
        "task_id": task_dir.name,
        "source_file": source_path.name,
        "passed": proc.returncode == 0,
        "latency_seconds": elapsed,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "response_text": text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded slice of the Aider polyglot benchmark."
    )
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:30000/v1"))
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--benchmark-dir", default=os.environ.get("BENCHMARK_DIR", str(DEFAULT_BENCHMARK_DIR)))
    parser.add_argument("--language", default=os.environ.get("LANGUAGE", "python"))
    parser.add_argument("--track", default=os.environ.get("TRACK", "practice"))
    parser.add_argument("--task-list", default=os.environ.get("TASK_LIST", str(DEFAULT_TASK_LIST)))
    parser.add_argument("--limit", type=int, default=os.environ.get("LIMIT"))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("MAX_TOKENS", "4096")))
    parser.add_argument("--output", default=os.environ.get("OUTPUT", str(DEFAULT_OUTPUT)))
    args = parser.parse_args()

    if args.language != "python":
        raise SystemExit("Only the Python polyglot track is supported by this runner right now.")

    model = args.model or detect_model(args.base_url)
    benchmark_dir = ensure_benchmark_repo(Path(args.benchmark_dir))
    benchmark_root = benchmark_dir / args.language / "exercises" / args.track
    if not benchmark_root.exists():
        raise SystemExit(f"Benchmark path not found: {benchmark_root}")
    task_list = Path(args.task_list) if args.task_list else None
    tasks = load_task_ids(task_list, benchmark_root, args.limit)
    if not tasks:
        raise SystemExit("No polyglot benchmark tasks selected.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    print(f"Model: {model}")
    for index, task_id in enumerate(tasks, start=1):
        print(f"[{index}/{len(tasks)}] Running {task_id}", flush=True)
        result = run_python_task(args.base_url, model, benchmark_root / task_id, args.max_tokens)
        results.append(result)
        passed = sum(1 for item in results if item["passed"])
        summary = {
            "base_url": args.base_url,
            "model": model,
            "language": args.language,
            "track": args.track,
            "task_count": len(tasks),
            "completed": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "results": results,
        }
        output_path.write_text(json.dumps(summary, indent=2))
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['task_id']}: {result['latency_seconds']:.2f}s", flush=True)
        if not result["passed"] and result["stderr"]:
            print(result["stderr"].strip(), flush=True)

    passed = sum(1 for result in results if result["passed"])
    summary = {
        "base_url": args.base_url,
        "model": model,
        "language": args.language,
        "track": args.track,
        "task_count": len(results),
        "completed": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    output_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary: {passed}/{len(results)} passed")
    print(f"Saved {output_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
