# Spark Arena Analysis

This note captures what was useful from reviewing Spark Arena, its linked tooling, and the DGX Spark forum discussions, and what should change in this repo as a result.

## Scope

Review date: `2026-03-24`

Sources reviewed:

- Spark Arena leaderboard and comparison tooling
- `sparkrun`
- `llama-benchy`
- `spark-vllm-docker`
- NVIDIA DGX Spark forum threads linked from the Spark Arena ecosystem

## What Spark Arena Adds

Spark Arena is useful for three things:

1. A common benchmark language for DGX Spark results
2. A shared recipe ecosystem for `vLLM`, `SGLang`, and related runtimes
3. A public compatibility signal for which model and runtime combinations actually work on Spark hardware

That matters for this repo because it reduces the amount of one-off benchmarking and recipe maintenance we need to do ourselves.

## What Spark Arena Does Not Settle

Spark Arena is primarily about deployment and inference performance, not coding-assistant quality.

It is strong evidence for:

- loadability on DGX Spark
- throughput under known prompt and decode workloads
- runtime and recipe choices

It is not strong evidence for:

- patch correctness on real repositories
- tool-calling reliability in IDE agents
- failure recovery quality
- autocomplete usefulness on real code
- overall suitability for confidential codebase work

Those still need local evaluation in this repo's intended workflow.

## Useful Lessons For This Repo

### 1. Use the same benchmark family when comparing configs

Spark Arena uses `llama-benchy`, so comparisons should not rely only on this repo's custom `bench.sh`.

Action taken:

- added [`scripts/bench-llama-benchy.sh`](../scripts/bench-llama-benchy.sh)

### 2. The current main-model flags are already aligned with the community direction

The Spark Arena and community recipes for `Qwen3-Coder-Next-FP8` reinforce several choices already present in this repo:

- `vLLM`
- `flashinfer`
- prefix caching
- `qwen3_coder` tool-call parser
- reduced context versus the model's headline maximum when practical limits matter

No default change was justified here.

### 3. `INT4` is promising for speed, but quality evidence is missing

The Spark Arena single-node `INT4` result for `Qwen3-Coder-Next-int4-AutoRound` is materially faster than the single-node `FP8` `vLLM` result.

However:

- the public `INT4` model card describes the quantization method, not coding-quality deltas
- the `FP8` model card's published quality charts are from the original pre-quantized model, not a direct `FP8` vs `INT4` comparison
- the `INT4` recipe is explicitly throughput-tuned

That means `INT4` should be treated as an experimental lane, not as the new default.

### 4. Spark Arena recipes are not apples-to-apples with this repo's default workflow

This repo optimizes for:

- a single DGX Spark
- stable agent/chat/edit behavior
- a separate autocomplete sidecar kept online

Many Spark Arena recipes optimize for:

- raw serving throughput
- main-model-only operation
- very large context lengths
- dual-node or cluster configurations

Those are useful references, but not direct replacements for the default stack here.

### 5. `SGLang` remains interesting, but not enough to replace the local default

Spark Arena shows strong `SGLang` throughput on dual-node `FP8`.

That does not overturn this repo's earlier conclusion:

- `SGLang` may be excellent for some Spark leaderboard workloads
- the local quality-first single-box deployment in this repo still favors the Spark-tuned `vLLM` path

## Relevant Benchmark Snapshot

Spark Arena snapshot inspected on `2026-03-24`:

| Configuration | Runtime | Nodes | Aggregate score | Prompt processing score | `tg128 (c1)` |
| --- | --- | --- | ---: | ---: | ---: |
| `Qwen3-Coder-Next-FP8` | `vllm` | `1` | `1137.62` | `2242.23` | `43.43 tok/s` |
| `Qwen3-Coder-Next-FP8` | `vllm` | `2` | `1629.08` | `3197.76` | `48.61 tok/s` |
| `Qwen3-Coder-Next-FP8` | `sglang` | `2` | `1603.93` | `3159.20` | `60.51 tok/s` |
| `Qwen3-Coder-Next-int4-AutoRound` | `vllm` | `1` | `1674.19` | `3260.35` | `70.72 tok/s` |

Important caveats:

- node count is not the same
- recipes are not the same
- the single-node `INT4` recipe is tuned for throughput
- these numbers say nothing direct about code quality

## Decision

Keep the current default stack unchanged:

- main assistant stays `Qwen/Qwen3-Coder-Next-FP8`
- main backend stays the Spark-tuned `vLLM` path
- autocomplete stays `Qwen/Qwen2.5-Coder-3B`
- default context stays `32k`

Add and use:

- Spark Arena-style benchmarking through `llama-benchy`
- a small repeatable coding-quality harness
- an explicit `FP8` vs `INT4` comparison plan before promoting any new default

## Why No Default Config Change Was Applied

The available evidence supports these conclusions:

- current defaults are already aligned with the community `vLLM` direction
- the repo's documented quality-first priorities still make sense
- the strongest `INT4` evidence is performance evidence, not quality evidence
- the throughput-oriented `INT4` flags should not be promoted blindly into a confidential-code assistant workflow

The right next step is evaluation, not replacement.
