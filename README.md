# DGX Spark VS Code Coding Assistant

This repo packages a working private coding-assistant stack for VS Code on a single NVIDIA DGX Spark.

It is built around:

- `Qwen/Qwen3-Coder-Next-FP8` as the main coding assistant for chat, edit, and agent-style work
- `Qwen/Qwen2.5-Coder-3B` as a separate autocomplete model
- `Continue` and `Cline` using OpenAI-compatible local endpoints
- a Spark-tuned `vLLM` image that was actually validated on DGX Spark hardware

If your priority is coding quality over raw speed, this is the best working setup we validated for `Qwen3-Coder-Next` on this box.

## What This Repo Gives You

- A `docker-compose.yml` that runs both the main assistant and a local autocomplete sidecar
- An optional `INT4` variant of the main service for side-by-side evaluation without changing the default startup path
- Persistent local model caches so weights are not re-downloaded on every restart
- A tested `Continue` config example in [`configs/continue-config.yaml`](./configs/continue-config.yaml)
- A tested `Cline` setup guide in [`configs/cline-openai-compatible.md`](./configs/cline-openai-compatible.md)
- Helper scripts to build, smoke-test, benchmark, and inspect the stack
- A `llama-benchy` wrapper for Spark Arena-style throughput checks
- A small coding-quality evaluation harness for repeatable model comparisons
- A bounded `RepoQA` runner for codebase-understanding checks
- A bounded `Aider` refactor runner for edit-quality checks
- A bounded `Aider polyglot` runner for feature-from-description checks
- A bounded `SWE-bench Lite` predictions runner plus official-harness evaluation wrapper
- A deeper write-up of the decisions and validation work in [`docs/validation-and-decisions.md`](./docs/validation-and-decisions.md)
- A Spark Arena follow-up analysis in [`docs/spark-arena-analysis.md`](./docs/spark-arena-analysis.md)
- A comparison plan for `FP8` vs `INT4` in [`docs/fp8-vs-int4-comparison-plan.md`](./docs/fp8-vs-int4-comparison-plan.md)
- A broader benchmark matrix in [`docs/benchmark-suite.md`](./docs/benchmark-suite.md)

## Tested Target

This repo was validated on:

- NVIDIA DGX Spark
- ARM64 host CPU
- NVIDIA GB10 GPU
- Docker Compose
- NVIDIA driver `580.142`

It is not an official turnkey NVIDIA recipe. It is a tested working path for this specific hardware and model combination.

## Default Stack

| Role | Model | Endpoint | Why |
| --- | --- | --- | --- |
| Main assistant | `Qwen/Qwen3-Coder-Next-FP8` | `http://localhost:30000/v1` | Best coding quality we validated for Continue/Cline-style work |
| Autocomplete | `Qwen/Qwen2.5-Coder-3B` | `http://localhost:30001/v1` | Better fit and better short completions than `1.5B`, while still leaving headroom for the main model |

## Quick Start

### 1. Prerequisites

- A DGX Spark with Docker and GPU container support working
- Access to pull models from Hugging Face
- Enough local disk space for model caches and compile artifacts

### 2. Build the local Spark-tuned `vLLM` image

```bash
./scripts/build-vllm-image.sh
```

By default the build script uses the tested `eugr/spark-vllm-docker` commit documented in the script.

### 3. Start the services

```bash
docker compose up -d
```

The default startup path keeps the `FP8` main model as the only main-assistant service. An `INT4` comparison service is defined, but it is behind the `int4` profile and does not start unless you explicitly ask for it.

### 4. Watch startup if you want to monitor the first load

```bash
docker compose logs -f qwen3-coder-next
docker compose logs -f qwen25-coder-autocomplete
```

### 5. Validate the deployment

Smoke-test both endpoints:

```bash
./scripts/smoke-test.sh
```

Run a small benchmark:

```bash
./scripts/bench.sh
```

Capture a quick system snapshot:

```bash
./scripts/system-snapshot.sh
```

Run Spark Arena-style throughput checks:

```bash
./scripts/bench-llama-benchy.sh
```

Run the small coding-quality harness:

```bash
./scripts/eval-quality.py
```

Run the broader benchmark suite:

```bash
./scripts/run-repoqa.py
./scripts/run-aider-refactor-benchmark.py
./scripts/run-aider-polyglot-benchmark.py
./scripts/run-swebench-lite.py
./scripts/run-swebench-lite-eval.py --predictions-path .results/swebench-lite-predictions.jsonl
```

## VS Code Setup

### Continue

Use the example config in [`configs/continue-config.yaml`](./configs/continue-config.yaml).

Model split:

- `Qwen3-Coder-Next-FP8` for `chat`, `edit`, and `apply`
- `Qwen2.5-Coder-3B` for `autocomplete`

### Cline

Use the values in [`configs/cline-openai-compatible.md`](./configs/cline-openai-compatible.md).

Recommended split:

- Use `Cline` for the main coding-agent workflow
- Use `Continue` for inline autocomplete

## Current Defaults

| Setting | Value |
| --- | --- |
| Main context | `32768` |
| Main GPU memory target | `0.72` |
| Main KV cache dtype | `fp8` |
| Main attention backend | `flashinfer` |
| Autocomplete context | `4096` |
| Autocomplete GPU memory target | `0.08` |

## Performance Snapshot

These are recent spot-check numbers from the current default stack on the test DGX Spark:

- Smoke test: main model returned `OK` in `0.93s`
- Smoke test: autocomplete returned a non-empty code completion in `2.65s`
- Bench: main coldish prompt `7.97s`
- Bench: main repeated prompt with prefix caching `2.37s`
- Bench: autocomplete short completion `1.56s`
- Observed GPU memory: main model about `88.8 GiB`
- Observed GPU memory: autocomplete about `11.0 GiB`
- Observed host memory available during the benchmark: about `15 GiB`

## Context Guidance

The default is `32k`, not because `40k` is impossible, but because `32k` is the better everyday tradeoff on a single Spark once you also keep autocomplete online.

What we validated:

- `32k` is stable with the current two-model setup
- `40k` is feasible on this hardware
- For very large application-wide refactors, it is still better to split the repo into sections and synthesize the results than to keep pushing context higher by default

That approach keeps the day-to-day interactive workflow faster and leaves more headroom for autocomplete and runtime stability.

## Useful Overrides

These are optional. The repo defaults are the tested settings.

```bash
MAIN_MAX_MODEL_LEN=40960 docker compose up -d qwen3-coder-next
AUTOCOMPLETE_MODEL=Qwen/Qwen2.5-Coder-7B docker compose up -d qwen25-coder-autocomplete
```

To compare `FP8` and `INT4` on the same box, keep the default `FP8` service stopped before starting the `INT4` profile because they share the same host port and the same GPU budget:

```bash
docker compose stop qwen3-coder-next
docker compose --profile int4 up -d qwen3-coder-next-int4
./scripts/bench.sh
./scripts/bench-llama-benchy.sh
./scripts/eval-quality.py
./scripts/run-repoqa.py
./scripts/run-aider-refactor-benchmark.py
./scripts/run-aider-polyglot-benchmark.py
./scripts/run-swebench-lite.py
./scripts/run-swebench-lite-eval.py --predictions-path .results/swebench-lite-predictions.jsonl
```

You can tune the alternate lane independently with:

```bash
MAIN_INT4_MODEL=Intel/Qwen3-Coder-Next-int4-AutoRound \
MAIN_INT4_MAX_MODEL_LEN=32768 \
MAIN_INT4_GPU_MEMORY_UTILIZATION=0.72 \
docker compose --profile int4 up -d qwen3-coder-next-int4
```

If you experiment with `7B` autocomplete, read the notes in [`docs/validation-and-decisions.md`](./docs/validation-and-decisions.md) first. It does fit on this box with `vLLM`, but it was slower and not clearly better enough to replace `3B` as the default.

## Caches And Persistence

Model weights and related caches are persisted on the host under:

- `${HOME}/.cache/huggingface`
- `${HOME}/.cache/vllm`
- `${HOME}/.cache/flashinfer`
- `${HOME}/.triton`

That means container restarts do not require full model re-downloads or full compile warmup from scratch every time.

## Why This Repo Uses This Path

The short version:

- `Qwen3-Coder-Next` was the highest-priority model because coding quality mattered most
- Stock Spark `SGLang` was not the best path for this main model in local testing
- A Spark-tuned `vLLM` image worked reliably on the DGX Spark for this workload
- `Qwen2.5-Coder-3B` was the best autocomplete tradeoff we found for the shared box

The full reasoning, compatibility notes, and measured comparisons live in [`docs/validation-and-decisions.md`](./docs/validation-and-decisions.md).

## Repository Layout

- [`docker-compose.yml`](./docker-compose.yml): main deployment
- [`scripts/build-vllm-image.sh`](./scripts/build-vllm-image.sh): builds the tested Spark-tuned `vLLM` image
- [`scripts/smoke-test.sh`](./scripts/smoke-test.sh): quick end-to-end validation
- [`scripts/bench.sh`](./scripts/bench.sh): simple performance spot checks
- [`scripts/bench-llama-benchy.sh`](./scripts/bench-llama-benchy.sh): Spark Arena-style benchmark wrapper
- [`scripts/eval-quality.py`](./scripts/eval-quality.py): small coding-quality regression harness
- [`scripts/run-repoqa.py`](./scripts/run-repoqa.py): bounded RepoQA runner for codebase-understanding comparisons
- [`scripts/run-aider-refactor-benchmark.py`](./scripts/run-aider-refactor-benchmark.py): bounded Aider refactor benchmark runner
- [`scripts/run-aider-polyglot-benchmark.py`](./scripts/run-aider-polyglot-benchmark.py): bounded Aider polyglot runner for feature implementation
- [`scripts/run-swebench-lite.py`](./scripts/run-swebench-lite.py): bounded SWE-bench Lite predictions runner using BM25 prompts
- [`scripts/run-swebench-lite-eval.py`](./scripts/run-swebench-lite-eval.py): wrapper for the official SWE-bench evaluation harness
- [`scripts/system-snapshot.sh`](./scripts/system-snapshot.sh): runtime resource snapshot
- [`evals/coding_tasks.json`](./evals/coding_tasks.json): task set used by the quality harness
- [`evals/aider-refactor-sample.txt`](./evals/aider-refactor-sample.txt): deterministic refactor sample used by the benchmark runner
- [`evals/aider-polyglot-python-sample.txt`](./evals/aider-polyglot-python-sample.txt): deterministic Aider polyglot Python sample
- [`evals/swebench-lite-sample.txt`](./evals/swebench-lite-sample.txt): deterministic SWE-bench Lite sample
- [`configs/continue-config.yaml`](./configs/continue-config.yaml): example Continue config
- [`configs/cline-openai-compatible.md`](./configs/cline-openai-compatible.md): Cline setup notes
- [`docs/validation-and-decisions.md`](./docs/validation-and-decisions.md): technical notes and rationale
- [`docs/spark-arena-analysis.md`](./docs/spark-arena-analysis.md): ecosystem analysis and recommendations
- [`docs/fp8-vs-int4-comparison-plan.md`](./docs/fp8-vs-int4-comparison-plan.md): comparison and promotion criteria
- [`docs/benchmark-suite.md`](./docs/benchmark-suite.md): expanded benchmark matrix and NVFP4 notes

## Caveats

- This repo is based on real validation, not an official support statement from NVIDIA, Qwen, Continue, or Cline.
- The main model path depends on a locally built Spark-tuned `vLLM` image.
- The numbers in this repo are practical spot checks for a coding-assistant workflow, not a formal benchmark suite.
