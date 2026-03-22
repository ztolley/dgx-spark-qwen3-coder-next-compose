# Validation And Decisions

This document explains what was tested, what worked, what did not, and why the repo defaults look the way they do.

## Goal

The goal was not to build the most "official" stack possible. The goal was to build the best private coding assistant for VS Code on a single DGX Spark, with these priorities:

1. Coding quality
2. Reliability on the real hardware
3. Ability to keep a separate autocomplete model online at the same time
4. Reasonable performance for interactive work

That is why the final default is centered on `Qwen/Qwen3-Coder-Next-FP8` first and everything else second.

## Final Decisions

| Area | Chosen default | Reason |
| --- | --- | --- |
| Main model | `Qwen/Qwen3-Coder-Next-FP8` | Best coding-assistant quality target for this project |
| Main backend | Spark-tuned `vLLM` image built locally as `vllm-node:latest` | This was the most reliable working path on the test DGX Spark |
| Main context | `32768` | Strong balance of utility, memory headroom, and coexistence with autocomplete |
| Autocomplete model | `Qwen/Qwen2.5-Coder-3B` | Better tradeoff than `1.5B`, and better fit than `7B` for the default shared-box setup |
| Autocomplete backend | `vLLM` | OpenAI-compatible, stable, and aligned well with Continue |

## What Was Tested

### Main model path

These paths were investigated during the work:

- NVIDIA NGC `vLLM` container
- Spark `SGLang`
- Spark-tuned community `vLLM`

What mattered in practice was not only "can the model load", but "can it load on this exact DGX Spark, stay stable, and still leave room for autocomplete".

The best result came from the Spark-tuned `vLLM` path built locally as `vllm-node:latest`.

### Why not stock `SGLang` for the main model

`SGLang` is attractive on paper for Spark, but it was not the best practical path for the main `Qwen3-Coder-Next` deployment on this machine during testing.

In local testing:

- the stock Spark `SGLang` route was not the stable path for the `80B` FP8 coding model
- the Spark-tuned `vLLM` route actually worked end to end
- once working, `vLLM` also gave useful prefix caching behavior for iterative coding workloads

### Why not an official NGC `vLLM` image

An NVIDIA NGC `vLLM` image was also checked earlier in the process, but the image version we tried expected a newer driver release than this machine had at the time. That made it a poor baseline for this repo, even before model-specific tuning.

## Context Size Decision

`Qwen3-Coder-Next` can tempt you into using very large context windows by default. On this box, the more practical answer was:

- default to `32k`
- use `40k` as an opt-in override when you really need it
- use external chunking and synthesis for very large repo-wide tasks instead of always paying the higher context cost

Why `32k` won as the default:

- it leaves more room for a second model
- it is already large enough for a lot of real codebase work
- it keeps the box in a healthier state for interactive use

What was validated:

- `32k` is stable with the main model and the autocomplete sidecar together
- `40k` was also feasible on this Spark
- a request with roughly `36k` prompt tokens was successfully served while autocomplete remained online

## Autocomplete Model Comparison

Several autocomplete candidates were explored.

### `Qwen2.5-Coder-1.5B`

Pros:

- very easy to fit
- low memory pressure

Cons:

- weaker completion quality
- some outputs looked dated or low-fidelity for modern code style

### `Qwen2.5-Coder-3B`

Pros:

- clearly better than `1.5B` for short code completions
- fit comfortably enough alongside the main model
- worked well through `vLLM` as an OpenAI-compatible endpoint

Cons:

- still not perfect on every prompt

This became the default.

### `Qwen2.5-Coder-7B`

There were two different stories depending on backend.

With `SGLang`:

- it was not a stable default alongside the main `80B` model
- the failure mode was memory reservation and runtime initialization pressure, not just the raw size of the weights

With `vLLM`:

- it did fit on the DGX Spark alongside the main model
- it loaded successfully with `4k` context
- it used noticeably more GPU memory than `3B`
- it was slower in short autocomplete-style spot checks
- it was not clearly better enough in output quality to justify becoming the default

### `3B` vs `7B` spot checks

These were quick autocomplete-style tests using short prompts, not a formal benchmark suite.

| Model | Python prompt | React prompt | Notes |
| --- | --- | --- | --- |
| `Qwen2.5-Coder-3B` | `2.64s` | `2.61s` | Faster, acceptable quality, current default |
| `Qwen2.5-Coder-7B` | `4.46s` | `6.08s` | Fit successfully, but slower and not clearly better enough |

Observed GPU memory while the main model stayed loaded:

| Model | Approximate GPU memory |
| --- | --- |
| Main `Qwen3-Coder-Next-FP8` | `88.8 GiB` |
| Autocomplete `Qwen2.5-Coder-3B` | `11.0 GiB` |
| Autocomplete `Qwen2.5-Coder-7B` | `17.3 GiB` |

That is why the repo default remains `3B`.

## Performance Notes

Recent spot checks on the default stack:

- smoke test: main model returned `OK` in `0.93s`
- smoke test: autocomplete returned a short code completion in `2.65s`
- bench: `main_coldish_prompt` in `7.97s`
- bench: `main_prefix_cache_repeat` in `2.37s`
- bench: `autocomplete_short_completion` in `1.56s`

The main practical performance insight was not just raw latency. It was that prefix caching provided a real improvement for repeated or highly similar prompts in an iterative coding workflow.

## Compatibility Notes

### Continue

The stack was validated as a local OpenAI-compatible setup for Continue:

- `chat`, `edit`, and `apply` mapped to `Qwen3-Coder-Next`
- `autocomplete` mapped to `Qwen2.5-Coder-3B`
- Continue state showed the expected models selected by role
- the VS Code remote session showed the Continue extension activating and probing the local endpoints

### Cline

The stack was also validated as an OpenAI-compatible target for Cline:

- Cline activated cleanly in the VS Code remote environment
- the main model endpoint and context window are documented in [`configs/cline-openai-compatible.md`](../configs/cline-openai-compatible.md)

### Persistence and downloads

Model downloads and related artifacts are kept in host-mounted caches under `${HOME}/.cache` and `${HOME}/.triton`.

That matters because:

- model downloads are large
- first-load compile and cache artifacts are valuable
- the goal is to make restarts practical

## What This Work Might Be Useful For Upstream

Yes, this work is potentially useful beyond this repo.

It could be useful to:

- NVIDIA and `vLLM`, as a real-world compatibility datapoint for DGX Spark, GB10, ARM64, Blackwell, and a large coding model that is not yet a turnkey Spark recipe
- Qwen, as deployment feedback for `Qwen3-Coder-Next` on Spark-class hardware and mixed-model local IDE workflows
- Continue and Cline, as an example of a working local split between a large chat/edit model and a separate autocomplete endpoint
- blog posts or community guides, because it includes actual memory, latency, and model tradeoff observations instead of only theoretical recommendations

What it is not:

- it is not an official certification
- it is not a vendor endorsement
- it is not a broad benchmark across many machines

It is best understood as a documented, working, quality-first reference setup for one important and somewhat unusual target: a single DGX Spark running a very capable local coding assistant.
