#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VENV = Path("/tmp/repoqa-venv")
DEFAULT_RESULT_DIR = ROOT_DIR / ".results" / "repoqa"


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_model(base_url: str) -> str:
    return get_json(base_url.rstrip("/") + "/models")["data"][0]["id"]


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def ensure_repoqa_venv(venv_dir: Path) -> Path:
    python_bin = venv_dir / "bin" / "python"
    repoqa_bin = venv_dir / "bin" / "repoqa.search_needle_function"
    if python_bin.exists() and repoqa_bin.exists():
        return python_bin

    run([sys.executable, "-m", "venv", str(venv_dir)])
    run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_bin), "-m", "pip", "install", "repoqa==0.1.2"])
    return python_bin


def build_subset_dataset(
    python_bin: Path,
    dataset_path: Path,
    languages: list[str],
    repos_per_language: int,
    needles_per_repo: int,
    env: dict[str, str],
) -> None:
    script = """
import json
import sys
from pathlib import Path

from repoqa.data import get_repoqa_data

dataset = get_repoqa_data()
languages = [lang for lang in sys.argv[2].split(",") if lang]
repos_per_language = int(sys.argv[3])
needles_per_repo = int(sys.argv[4])

subset = {}
for lang in languages:
    repos = dataset.get(lang, [])
    picked = []
    for repo in repos[:repos_per_language]:
        repo = dict(repo)
        repo["needles"] = repo.get("needles", [])[:needles_per_repo]
        if repo["needles"]:
            picked.append(repo)
    if picked:
        subset[lang] = picked

Path(sys.argv[1]).write_text(json.dumps(subset))
"""
    run(
        [
            str(python_bin),
            "-c",
            script,
            str(dataset_path),
            ",".join(languages),
            str(repos_per_language),
            str(needles_per_repo),
        ],
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded RepoQA slice against an OpenAI-compatible endpoint.")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:30000/v1"))
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--languages", default=os.environ.get("LANGUAGES", "python"))
    parser.add_argument("--repos-per-language", type=int, default=int(os.environ.get("REPOS_PER_LANGUAGE", "5")))
    parser.add_argument("--needles-per-repo", type=int, default=int(os.environ.get("NEEDLES_PER_REPO", "3")))
    parser.add_argument("--code-context-size", type=int, default=int(os.environ.get("CODE_CONTEXT_SIZE", "16384")))
    parser.add_argument("--max-new-tokens", type=int, default=int(os.environ.get("MAX_NEW_TOKENS", "1024")))
    parser.add_argument("--result-dir", default=os.environ.get("RESULT_DIR", str(DEFAULT_RESULT_DIR)))
    parser.add_argument("--venv-dir", default=os.environ.get("REPOQA_VENV", str(DEFAULT_VENV)))
    args = parser.parse_args()

    model = args.model or detect_model(args.base_url)
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    hf_home = result_dir / ".hf-home"
    hf_home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("HF_HOME", str(hf_home))
    env.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))
    env.setdefault("TRANSFORMERS_CACHE", str(hf_home / "transformers"))
    env.setdefault("HF_HUB_DISABLE_XET", "1")

    venv_dir = Path(args.venv_dir)
    python_bin = ensure_repoqa_venv(venv_dir)
    repoqa_bin = venv_dir / "bin" / "repoqa.search_needle_function"

    model_slug = model.replace("/", "_slash_")
    dataset_path = result_dir / f"repoqa-subset-{model_slug}.json"
    build_subset_dataset(
        python_bin,
        dataset_path,
        languages=languages,
        repos_per_language=args.repos_per_language,
        needles_per_repo=args.needles_per_repo,
        env=env,
    )

    run(
        [
            str(repoqa_bin),
            "--base-url",
            args.base_url,
            "--model",
            model,
            "--backend",
            "openai",
            "--dataset-path",
            str(dataset_path),
            "--code-context-size",
            str(args.code_context_size),
            "--max-new-tokens",
            str(args.max_new_tokens),
            "--result-dir",
            str(result_dir),
        ],
        env=env,
    )

    score_path = result_dir / f"ntoken_{args.code_context_size}" / f"{model_slug}-SCORES.json"
    if score_path.exists():
        score = json.loads(score_path.read_text())
        print(f"Model: {model}")
        print(f"Saved {score_path}")
        print(json.dumps(score, indent=2))
    else:
        print(f"RepoQA finished but score file was not found at {score_path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
