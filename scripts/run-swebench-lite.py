#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VENV = Path("/tmp/swebench-lite-venv")
DEFAULT_OUTPUT = ROOT_DIR / ".results" / "swebench-lite-predictions.jsonl"
DEFAULT_DATASET = "princeton-nlp/SWE-bench_Lite_bm25_13K"
DEFAULT_INSTANCE_FILE = ROOT_DIR / "evals" / "swebench-lite-sample.txt"


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


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
    with urllib.request.urlopen(req, timeout=1200) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_model(base_url: str) -> str:
    return get_json(base_url.rstrip("/") + "/models")["data"][0]["id"]


def ensure_venv(venv_dir: Path) -> Path:
    python_bin = venv_dir / "bin" / "python"
    if not python_bin.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
        run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_bin), "-m", "pip", "install", "datasets"])
    return python_bin


def maybe_reexec_in_venv(python_bin: Path) -> None:
    if os.environ.get("_SWEBENCH_LITE_BOOTSTRAPPED") == "1":
        return
    env = os.environ.copy()
    env["_SWEBENCH_LITE_BOOTSTRAPPED"] = "1"
    os.execve(str(python_bin), [str(python_bin), str(Path(__file__).resolve()), *sys.argv[1:]], env)


def extract_diff(response: str | None) -> str | None:
    if response is None:
        return None
    diff_matches: list[str] = []
    other_matches: list[str] = []
    patterns = [
        re_compile(r"\<([\w-]+)\>(.*?)\<\/\1\>"),
        re_compile(r"```(\w+)?\n(.*?)```"),
    ]
    for pattern in patterns:
        for code, match in pattern.findall(response):
            if code in {"diff", "patch"}:
                diff_matches.append(match)
            else:
                other_matches.append(match)
    if diff_matches:
        return diff_matches[0]
    if other_matches:
        return other_matches[0]
    return response.split("</s>")[0]


def re_compile(pattern: str):
    import re

    return re.compile(pattern, re.DOTALL)


def load_instance_ids(instance_file: Path | None, cli_ids: list[str] | None) -> list[str]:
    if cli_ids:
        return cli_ids
    if instance_file and instance_file.exists():
        return [line.strip() for line in instance_file.read_text().splitlines() if line.strip()]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate bounded SWE-bench Lite predictions against an OpenAI-compatible endpoint."
    )
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:30000/v1"))
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--dataset-name", default=os.environ.get("DATASET_NAME", DEFAULT_DATASET))
    parser.add_argument("--split", default=os.environ.get("SPLIT", "test"))
    parser.add_argument("--limit", type=int, default=os.environ.get("LIMIT"))
    parser.add_argument("--instance-id", action="append", dest="instance_ids")
    parser.add_argument("--instance-file", default=os.environ.get("INSTANCE_FILE", str(DEFAULT_INSTANCE_FILE)))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("MAX_TOKENS", "4096")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TEMPERATURE", "0")))
    parser.add_argument("--output", default=os.environ.get("OUTPUT", str(DEFAULT_OUTPUT)))
    parser.add_argument("--venv-dir", default=os.environ.get("SWEBENCH_LITE_VENV", str(DEFAULT_VENV)))
    args = parser.parse_args()

    venv_python = ensure_venv(Path(args.venv_dir))
    maybe_reexec_in_venv(venv_python)

    from datasets import load_dataset

    model = args.model or detect_model(args.base_url)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    hf_home = output_path.parent / ".hf-home"
    hf_home.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HF_HUB_CACHE"] = str(hf_home / "hub")
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_home / "hub")
    os.environ["HF_DATASETS_CACHE"] = str(hf_home / "datasets")
    os.environ["TRANSFORMERS_CACHE"] = str(hf_home / "transformers")
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    dataset = load_dataset(args.dataset_name, split=args.split, cache_dir=str(hf_home / "datasets"))
    instance_ids = load_instance_ids(Path(args.instance_file) if args.instance_file else None, args.instance_ids)
    if instance_ids:
        wanted = set(instance_ids)
        dataset = dataset.filter(lambda item: item["instance_id"] in wanted, load_from_cache_file=False)
    if args.limit is not None:
        dataset = dataset.select(range(min(int(args.limit), len(dataset))))
    if len(dataset) == 0:
        raise SystemExit("No SWE-bench Lite instances selected.")

    existing_ids: set[str] = set()
    if output_path.exists():
        with output_path.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                existing_ids.add(json.loads(line)["instance_id"])

    summary_path = output_path.with_suffix(".summary.json")
    summary: dict[str, object] = {
        "base_url": args.base_url,
        "model": model,
        "dataset_name": args.dataset_name,
        "split": args.split,
        "attempted": 0,
        "completed": 0,
        "results": [],
    }

    with output_path.open("a") as handle:
        for index, item in enumerate(dataset, start=1):
            instance_id = item["instance_id"]
            if instance_id in existing_ids:
                continue
            print(f"[{index}/{len(dataset)}] Running {instance_id}", flush=True)
            prompt = item["text"]
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
            }
            record: dict[str, object] = {
                "instance_id": instance_id,
                "model_name_or_path": model,
            }
            summary["attempted"] = int(summary["attempted"]) + 1
            try:
                response = post_json(args.base_url.rstrip("/") + "/chat/completions", payload)
                completion = response["choices"][0]["message"]["content"]
                usage = response.get("usage") or {}
                record.update(
                    {
                        "full_output": completion,
                        "model_patch": extract_diff(completion),
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                    }
                )
                print(json.dumps(record), file=handle, flush=True)
                summary["completed"] = int(summary["completed"]) + 1
                status = "OK" if record["model_patch"] else "EMPTY_PATCH"
                print(f"{status} {instance_id}", flush=True)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                record.update({"model_patch": "", "error": f"HTTP {exc.code}", "error_body": body})
                print(json.dumps(record), file=handle, flush=True)
                print(f"HTTP {exc.code} {instance_id}", flush=True)
            except Exception as exc:  # pragma: no cover - best effort wrapper
                record.update({"model_patch": "", "error": str(exc)})
                print(json.dumps(record), file=handle, flush=True)
                print(f"ERROR {instance_id}: {exc}", flush=True)
            summary["results"].append(
                {
                    "instance_id": instance_id,
                    "has_patch": bool(record.get("model_patch")),
                    "error": record.get("error"),
                }
            )
            summary_path.write_text(json.dumps(summary, indent=2))

    print(f"Model: {model}")
    print(f"Saved predictions to {output_path}")
    print(f"Saved summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
