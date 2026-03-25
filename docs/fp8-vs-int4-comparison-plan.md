# FP8 vs INT4 Comparison Plan

This plan exists so future `FP8` vs `INT4` decisions are made on repeatable evidence instead of leaderboard intuition.

## Goal

Pick the best local coding-assistant setup for confidential codebases and data on a DGX Spark.

The winning profile is not the one with the highest tokens/sec. It is the one that best balances:

1. coding quality
2. runtime stability
3. acceptable latency
4. ability to keep autocomplete online
5. operational simplicity

## Profiles To Compare

### Baseline: Current default

- Main: `Qwen/Qwen3-Coder-Next-FP8`
- Main backend: Spark-tuned `vLLM`
- Context: `32768`
- Autocomplete: `Qwen/Qwen2.5-Coder-3B`

### Experimental A: FP8 main-only

Use when you want an apples-to-apples comparison against Spark Arena-style main-model benchmarks without the autocomplete sidecar affecting headroom.

### Experimental B: INT4 main-only

- Main: `Intel/Qwen3-Coder-Next-int4-AutoRound`
- Backend: `vLLM`
- Use the throughput-tuned recipe as a starting point, but do not assume its flags are automatically right for IDE use

### Experimental C: INT4 plus autocomplete

Only worth considering if:

- it fits cleanly
- it stays stable
- it does not regress quality

## Benchmark Sequence

### 1. Health and spot checks

Run:

```bash
./scripts/smoke-test.sh
./scripts/bench.sh
```

Purpose:

- confirm the endpoints are alive
- confirm prefix caching behavior
- establish simple latency numbers close to the repo's historical data

### 2. Spark Arena-style throughput benchmark

Run:

```bash
./scripts/bench-llama-benchy.sh
```

Recommended env overrides for the current default:

```bash
RUNS=3 DEPTHS="0 24576" ./scripts/bench-llama-benchy.sh
```

Recommended env overrides for a larger-context experimental lane:

```bash
RUNS=3 DEPTHS="0 32768" RESPONSE_TOKENS=64 ./scripts/bench-llama-benchy.sh
```

Purpose:

- compare with the same benchmark family used by Spark Arena
- measure decode speed, prompt ingest, and cached-context behavior

### 3. Coding-quality regression check

Run:

```bash
./scripts/eval-quality.py
```

Purpose:

- score deterministic small coding tasks through pass/fail tests
- create a baseline for later `INT4` comparison

### 4. Confidential repository manual eval

This is mandatory before promoting any new default.

Use a small, repeatable task set from a real confidential codebase:

- implement a small feature
- fix a real bug with tests
- refactor a multi-file change
- recover from a failed tool or command
- answer a codebase question that requires cross-file reasoning

Judge:

- correctness
- number of repair turns needed
- hallucinated file or symbol rate
- ability to stay inside project conventions

## Promotion Criteria

Promote `INT4` only if all of the following are true:

1. No meaningful regression in `./scripts/eval-quality.py`
2. No obvious regression in confidential-repo manual tasks
3. Stable startup and repeatable runs
4. Enough remaining memory headroom to keep the chosen autocomplete setup online
5. Faster latency or materially better throughput in a way that improves the real IDE workflow

If `INT4` is faster but worse at code tasks, it stays experimental.

## Flags To Treat As Experimental

The latest Spark Arena `INT4` recipe uses several throughput-oriented knobs:

- `--enable-chunked-prefill`
- `--max-num-seqs 128`
- `--max-num-batched-tokens 16384`
- `--performance-mode throughput`
- `--mamba-cache-mode align`

These should be benchmarked and reviewed, not copied blindly into the default stack.

## What To Record

For each run, keep:

- commit SHA of this repo
- `spark-vllm-docker` ref used to build
- model name
- runtime
- main context
- whether autocomplete was online
- `bench.sh` summary
- `bench-llama-benchy.sh` JSON output
- `eval-quality.py` JSON output
- manual notes from confidential-repo tasks

## Current Recommendation

As of `2026-03-24`, the default remains:

- `Qwen/Qwen3-Coder-Next-FP8`
- Spark-tuned `vLLM`
- `32k` context
- `Qwen/Qwen2.5-Coder-3B` autocomplete

The next candidate to test is `INT4`, but only as an experiment against this baseline.
