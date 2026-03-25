# Benchmark Suite

This benchmark suite exists to answer a practical question:

Which model profile is best for a confidential local coding assistant on a DGX Spark?

The answer needs more than tokens per second. It needs evidence across:

1. codebase understanding
2. refactoring correctness
3. feature implementation from a description
4. repo-level bug fixing
5. runtime latency and stability

## Benchmark Matrix

| Signal | Benchmark | What it tells you |
| --- | --- | --- |
| Throughput and latency | `scripts/bench.sh`, `scripts/bench-llama-benchy.sh` | Whether the profile is fast enough for an interactive IDE workflow |
| Codebase understanding | `scripts/run-repoqa.py` | Whether the model can localize the right code inside a larger repo |
| Refactoring quality | `scripts/run-aider-refactor-benchmark.py` | Whether the model can perform structural edits in real code and keep them valid |
| Feature implementation | `scripts/run-aider-polyglot-benchmark.py` | Whether the model can implement behavior from a natural-language spec |
| Repo-level bug fixing | `scripts/run-swebench-lite.py` plus `scripts/run-swebench-lite-eval.py` | Whether the model can produce patches that resolve real GitHub issues under the official harness |
| Small local regression check | `scripts/eval-quality.py` | A fast sanity check before spending time on the larger suites |

## Recommended Run Order

Use the fast checks first:

```bash
./scripts/smoke-test.sh
./scripts/bench.sh
./scripts/eval-quality.py
```

Then move to broader coding tasks:

```bash
./scripts/run-repoqa.py
./scripts/run-aider-refactor-benchmark.py
./scripts/run-aider-polyglot-benchmark.py
```

Then use the heavier repo-level benchmark:

```bash
./scripts/run-swebench-lite.py
./scripts/run-swebench-lite-eval.py --predictions-path .results/swebench-lite-predictions.jsonl
```

## What A Definitive FP8 vs INT4 Answer Requires

Promote `INT4` over `FP8` only if all of the following hold:

1. no clear regression in `RepoQA`
2. no clear regression in `Aider refactor`
3. no clear regression in `Aider polyglot`
4. no clear regression in `SWE-bench Lite`
5. faster latency or materially better throughput
6. stable serving behavior with the autocomplete sidecar online

If `INT4` is faster but loses on repo-level bug fixing or real edits, it stays experimental.

## NVFP4 Track

`NVFP4` should be treated as a separate experiment track, not as a drop-in replacement for the current `vLLM` stack.

Why:

- NVIDIA's current compression guidance recommends `NVFP4` on Blackwell-class GPUs for maximum compression.
- NVIDIA's TensorRT-LLM docs include `Qwen3Next` support.
- NVIDIA's Model Optimizer docs mention `Qwen 3, 2.5 (FP8, NVFP4)` in the unified HuggingFace checkpoint support matrix.
- But the same Model Optimizer deployment page still says `vLLM` deployment currently supports `fp8` quantized models.
- We do not currently have an official published `Qwen3-Coder-Next-NVFP4` checkpoint or an official `Qwen3Next` `NVFP4` recipe for this repo's current `vLLM` path.

So the practical interpretation is:

- `NVFP4` is plausible on this hardware
- it is likely a `TensorRT-LLM` experiment first
- it is not yet a straightforward `docker-compose.yml` swap for the current `vLLM` deployment

## Interpreting NVFP4 vs INT4

At a high level:

- `INT4` is integer quantization and is usually simpler and widely available
- `NVFP4` is NVIDIA's 4-bit floating-point format tuned for Blackwell hardware
- `NVFP4` is generally aimed at keeping more numerical fidelity than plain `INT4` while still compressing aggressively

That does not guarantee better coding quality on this specific model. It only means `NVFP4` is the more promising 4-bit format to test on supported Blackwell tooling.
