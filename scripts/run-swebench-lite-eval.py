#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VENV = Path("/tmp/swebench-eval-venv")
DEFAULT_WORK_DIR = ROOT_DIR / ".results" / "swebench-eval"
DEFAULT_DATASET = "princeton-nlp/SWE-bench_Lite"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_venv(venv_dir: Path) -> Path:
    python_bin = venv_dir / "bin" / "python"
    if not python_bin.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
        run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_bin), "-m", "pip", "install", "swebench"])
    return python_bin


def parse_prediction_ids(predictions_path: Path) -> list[str]:
    ids: list[str] = []
    with predictions_path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            ids.append(json.loads(line)["instance_id"])
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the official SWE-bench Lite evaluation harness against a predictions file."
    )
    parser.add_argument("--predictions-path", required=True)
    parser.add_argument("--dataset-name", default=os.environ.get("DATASET_NAME", DEFAULT_DATASET))
    parser.add_argument("--split", default=os.environ.get("SPLIT", "test"))
    parser.add_argument("--run-id", default=os.environ.get("RUN_ID", "local-swebench-lite"))
    parser.add_argument("--max-workers", type=int, default=int(os.environ.get("MAX_WORKERS", "1")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("TIMEOUT", "1800")))
    parser.add_argument("--cache-level", default=os.environ.get("CACHE_LEVEL", "env"))
    parser.add_argument("--clean", action="store_true", default=os.environ.get("CLEAN", "").lower() == "true")
    parser.add_argument("--namespace", default=os.environ.get("NAMESPACE"))
    parser.add_argument("--work-dir", default=os.environ.get("WORK_DIR", str(DEFAULT_WORK_DIR)))
    parser.add_argument("--venv-dir", default=os.environ.get("SWEBENCH_EVAL_VENV", str(DEFAULT_VENV)))
    args = parser.parse_args()

    predictions_path = Path(args.predictions_path).resolve()
    if not predictions_path.exists():
        raise SystemExit(f"Predictions file not found: {predictions_path}")

    python_bin = ensure_venv(Path(args.venv_dir))
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    namespace = args.namespace
    if namespace is None:
        namespace = "none" if platform.machine().lower() in {"arm64", "aarch64"} else "swebench"

    instance_ids = parse_prediction_ids(predictions_path)
    if not instance_ids:
        raise SystemExit("Predictions file did not contain any instance ids.")

    cmd = [
        str(python_bin),
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        args.dataset_name,
        "--split",
        args.split,
        "--predictions_path",
        str(predictions_path),
        "--max_workers",
        str(args.max_workers),
        "--timeout",
        str(args.timeout),
        "--cache_level",
        args.cache_level,
        "--clean",
        "true" if args.clean else "false",
        "--run_id",
        args.run_id,
        "--namespace",
        namespace,
        "--instance_ids",
        *instance_ids,
    ]
    run(cmd, cwd=work_dir)

    report_name = predictions_path.stem.replace("/", "__") + f".{args.run_id}.json"
    print(f"Evaluation finished in {work_dir}")
    print("The official harness writes its report JSON into the working directory.")
    print(f"Expected report name pattern: {report_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
