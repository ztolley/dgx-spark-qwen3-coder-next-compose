#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
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
DEFAULT_BENCHMARK_DIR = Path("/tmp/refactor-benchmark")
DEFAULT_TASK_LIST = ROOT_DIR / "evals" / "aider-refactor-sample.txt"
DEFAULT_OUTPUT = ROOT_DIR / ".results" / "aider-refactor.json"
BENCHMARK_REPO = "https://github.com/Aider-AI/refactor-benchmark.git"

REFACTOR_TOOLS = """\
import ast


class ParentNodeTransformer(ast.NodeTransformer):
    def generic_visit(self, node):
        for child in ast.iter_child_nodes(node):
            child.parent = node
        return super().generic_visit(node)


def verify_full_func_at_top_level(tree, func, func_children):
    func_nodes = [
        item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == func
    ]
    assert func_nodes, f"Function {func} not found"
    for func_node in func_nodes:
        if not isinstance(func_node.parent, ast.Module):
            continue
        num_children = sum(1 for _ in ast.walk(func_node))
        pct_diff = abs(num_children - func_children) * 100 / func_children
        assert pct_diff < 10, f"Old method had {func_children} children, new method has {num_children}"
        return
    raise AssertionError(f"{func} is not a top level function")


def verify_old_class_children(tree, old_class, old_class_children):
    node = next(
        (item for item in ast.walk(tree) if isinstance(item, ast.ClassDef) and item.name == old_class),
        None,
    )
    assert node is not None, f"Old class {old_class} not found"
    num_children = sum(1 for _ in ast.walk(node))
    pct_diff = abs(num_children - old_class_children) * 100 / old_class_children
    assert pct_diff < 10, f"Old class had {old_class_children} children, new class has {num_children}"


def verify_refactor(fname, func, func_children, old_class, old_class_children):
    with open(fname, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    ParentNodeTransformer().visit(tree)
    verify_full_func_at_top_level(tree, func, func_children)
    verify_old_class_children(tree, old_class, old_class_children - func_children)
"""


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
    return text.strip() + "\n"


def ensure_benchmark_repo(repo_dir: Path) -> Path:
    if (repo_dir / ".git").exists():
        return repo_dir
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", BENCHMARK_REPO, str(repo_dir)])
    return repo_dir


def find_source_and_test(task_dir: Path) -> tuple[Path, Path]:
    py_files = sorted(task_dir.glob("*.py"))
    test_files = [path for path in py_files if path.stem.endswith("_test")]
    source_files = [path for path in py_files if path not in test_files]
    if len(source_files) != 1 or len(test_files) != 1:
        raise RuntimeError(f"Expected one source file and one test file in {task_dir}")
    return source_files[0], test_files[0]


def load_task_ids(task_list: Path | None, benchmark_root: Path, limit: int | None) -> list[str]:
    if task_list and task_list.exists():
        tasks = [line.strip() for line in task_list.read_text().splitlines() if line.strip()]
    else:
        tasks = sorted(path.name for path in benchmark_root.iterdir() if path.is_dir())
    if limit is not None:
        tasks = tasks[:limit]
    return tasks


def run_task(base_url: str, model: str, task_dir: Path, max_tokens: int) -> dict:
    source_path, test_path = find_source_and_test(task_dir)
    instructions = (task_dir / ".docs" / "instructions.md").read_text()
    source_text = source_path.read_text()

    prompt = (
        "You are being evaluated on a Python refactoring task.\n"
        "Apply the instructions to the file below.\n"
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

    with tempfile.TemporaryDirectory(prefix=f"refactor-{task_dir.name}-") as td:
        temp_dir = Path(td)
        work_dir = temp_dir / task_dir.name
        shutil.copytree(task_dir, work_dir)
        benchmark_pkg = temp_dir / "benchmark"
        benchmark_pkg.mkdir()
        (benchmark_pkg / "__init__.py").write_text("")
        (benchmark_pkg / "refactor_tools.py").write_text(REFACTOR_TOOLS)
        (work_dir / source_path.name).write_text(candidate)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(temp_dir)
        proc = subprocess.run(
            [sys.executable, str(work_dir / test_path.name)],
            cwd=work_dir,
            capture_output=True,
            text=True,
            env=env,
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
    parser = argparse.ArgumentParser(description="Run a bounded slice of Aider's refactor benchmark.")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:30000/v1"))
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--benchmark-dir", default=os.environ.get("BENCHMARK_DIR", str(DEFAULT_BENCHMARK_DIR)))
    parser.add_argument("--task-list", default=os.environ.get("TASK_LIST", str(DEFAULT_TASK_LIST)))
    parser.add_argument("--limit", type=int, default=os.environ.get("LIMIT"))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("MAX_TOKENS", "6144")))
    parser.add_argument("--output", default=os.environ.get("OUTPUT", str(DEFAULT_OUTPUT)))
    args = parser.parse_args()

    model = args.model or detect_model(args.base_url)
    benchmark_dir = ensure_benchmark_repo(Path(args.benchmark_dir))
    benchmark_root = benchmark_dir / "refactor-benchmark"
    task_list = Path(args.task_list) if args.task_list else None
    tasks = load_task_ids(task_list, benchmark_root, args.limit)
    if not tasks:
        print("No refactor benchmark tasks selected.", file=sys.stderr)
        return 1

    results = [
        run_task(args.base_url, model, benchmark_root / task_id, args.max_tokens)
        for task_id in tasks
    ]
    passed = sum(1 for result in results if result["passed"])
    summary = {
        "base_url": args.base_url,
        "model": model,
        "task_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2))

    print(f"Model: {model}")
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['task_id']}: {result['latency_seconds']:.2f}s")
        if not result["passed"] and result["stderr"]:
            print(result["stderr"].strip())
    print(f"Summary: {passed}/{len(results)} passed")
    print(f"Saved {output_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
