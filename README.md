# Qwen3-Coder-Next on DGX Spark

This repo packages a tested DGX Spark setup for:

- `Qwen/Qwen3-Coder-Next-FP8` as the main coding assistant
- `Qwen/Qwen2.5-Coder-3B` as an OpenAI-compatible autocomplete sidecar

Both services use a Spark-specific `vllm-node:latest` image built from `eugr/spark-vllm-docker`. The main service also applies the Qwen3-Coder-Next fixes in [`vllm-mods/fix-qwen3-coder-next`](./vllm-mods/fix-qwen3-coder-next). On this machine, that path proved more reliable than the stock `sglang:spark` image for the 80B FP8 model.

## Why this layout

- `Qwen3-Coder-Next` is the higher-quality coding assistant for Continue/Cline.
- `vllm-node:latest` is the working Spark/Blackwell path we validated locally for this model.
- `flashinfer` plus `--enable-prefix-caching` materially helps iterative coding workflows.
- A separate `Qwen2.5-Coder-3B` autocomplete model gives better code completions than `1.5B` while still fitting beside the main assistant.

## Tested result on this Spark

- Main model context: `32768`
- Main model GPU memory target: `0.72`
- Autocomplete context: `4096`
- Autocomplete GPU memory target: `0.08`
- Observed GPU memory with both services up:
  - main model: about `89 GiB`
  - autocomplete: about `13.5 GiB`
- Host RAM remained healthy during validation, with about `14 GiB` still available.

## Prerequisites

- DGX Spark with current NVIDIA driver and container toolkit
- Docker Compose
- Access to pull models from Hugging Face
- Local `vllm-node:latest` image built first

## Build the local vLLM image

```bash
./scripts/build-vllm-image.sh
```

By default this builds the tested `eugr/spark-vllm-docker` commit:

- repo: `https://github.com/eugr/spark-vllm-docker.git`
- ref: `2d749742e410a9467ca44cab354056e86015b6e8`

## Start the services

```bash
docker compose up -d
```

Watch startup:

```bash
docker compose logs -f qwen3-coder-next
docker compose logs -f qwen25-coder-autocomplete
```

## Validate the deployment

Smoke-test both endpoints:

```bash
./scripts/smoke-test.sh
```

Run a small benchmark and capture a system snapshot:

```bash
./scripts/bench.sh
```

## Useful overrides

These are optional. The compose file already has sane defaults.

```bash
MAIN_MAX_MODEL_LEN=24576 docker compose up -d qwen3-coder-next
AUTOCOMPLETE_MODEL=Qwen/Qwen2.5-Coder-1.5B docker compose up -d qwen25-coder-autocomplete
```

Default ports:

- main assistant: `http://localhost:30000/v1`
- autocomplete: `http://localhost:30001`

## Continue and Cline

Use the main service as your chat/agent model:

- base URL: `http://<spark-host>:30000/v1`
- model: `Qwen/Qwen3-Coder-Next-FP8`

Use the autocomplete service separately:

- base URL: `http://<spark-host>:30001/v1`
- model: `Qwen/Qwen2.5-Coder-3B`
- Continue config example: [`configs/continue-config.yaml`](./configs/continue-config.yaml)
- Cline setup guide: [`configs/cline-openai-compatible.md`](./configs/cline-openai-compatible.md)
- A matching Continue config was also written locally to `~/.continue/config.yaml`

## Notes on efficiency

For this exact box, this is the best practical path we validated for `Qwen3-Coder-Next`:

- stock Spark `SGLang` was not stable for the main model on GB10/Blackwell in our testing
- the Spark-tuned community `vLLM` build worked and handled the full `32k` context
- `Qwen2.5-Coder-3B` under `vLLM` was the best autocomplete tradeoff we found that both fit on the Spark and matched Continue's preferred `vLLM` integration path
- NVIDIA's official Spark docs now list DGX Spark support in vLLM, but `Qwen3-Coder-Next` is still not in the official Spark support matrix, so this remains a tested best-known path rather than an official NVIDIA turnkey recipe

## Published model caches

Model weights are persisted in host caches under `${HOME}/.cache`, so restarts do not need a full re-download.
