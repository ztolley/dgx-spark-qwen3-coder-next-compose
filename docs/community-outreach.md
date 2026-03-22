# Community Outreach Drafts

This page contains ready-to-post drafts for sharing this repo with communities that may find it useful.

Repo:

- `https://github.com/ztolley/dgx-spark-qwen3-coder-next-compose`

Current docs to link:

- [`README.md`](../README.md)
- [`validation-and-decisions.md`](./validation-and-decisions.md)

## Core Message

Use this as the base idea across all communities:

- this is a tested, working DGX Spark setup for `Qwen/Qwen3-Coder-Next-FP8`
- it is focused on VS Code coding assistance with `Continue` and `Cline`
- it uses a Spark-tuned `vLLM` path because that was the most reliable option we validated on this hardware
- it keeps a second local autocomplete model online at the same time
- it includes real memory, context, and latency observations

## Draft: NVIDIA Forum

Suggested title:

`Tested DGX Spark setup for Qwen3-Coder-Next FP8 + local VS Code coding assistant`

Suggested post:

```text
I wanted to share a tested DGX Spark setup for anyone trying to run a private VS Code coding assistant locally on this box.

Repo:
https://github.com/ztolley/dgx-spark-qwen3-coder-next-compose

What this setup does:
- Runs Qwen/Qwen3-Coder-Next-FP8 as the main coding assistant
- Runs a separate Qwen2.5-Coder-3B autocomplete model alongside it
- Exposes both as local OpenAI-compatible endpoints for Continue and Cline
- Persists Hugging Face/vLLM/FlashInfer caches so restarts do not re-download everything

Why this may be useful:
- This was validated on a real DGX Spark with GB10 + ARM64
- I tried multiple paths during setup, and the Spark-tuned vLLM route was the most reliable working path for Qwen3-Coder-Next on this hardware
- The repo documents the reasoning, tradeoffs, and measured memory/performance numbers

Current default setup:
- Main model: Qwen/Qwen3-Coder-Next-FP8
- Main context: 32768
- Autocomplete model: Qwen/Qwen2.5-Coder-3B

Recent spot-check numbers from the current default stack:
- Main coldish prompt: 7.97s
- Main repeated prompt with prefix caching: 2.37s
- Autocomplete short completion: 1.56s
- GPU memory: main model about 88.8 GiB
- GPU memory: autocomplete about 11.0 GiB

I also tested 40k context and it was feasible, but I kept 32k as the default because it is the better day-to-day tradeoff once autocomplete is also running.

If this is useful to anyone else working on Spark, I hope it saves some time. Feedback and comparisons with other Spark-native paths would be welcome.
```

Best places to post:

- reply in the existing thread about running `Qwen3-Coder-Next` on Spark
- create a separate DGX Spark project post with the repo link

## Draft: vLLM Forum Or GitHub Discussion

Suggested title:

`DGX Spark / GB10 reference setup for Qwen3-Coder-Next FP8 + Qwen2.5-Coder-3B autocomplete`

Suggested post:

```text
I wanted to share a real-world DGX Spark deployment reference for anyone working with vLLM on GB10 / ARM64 / Blackwell hardware.

Repo:
https://github.com/ztolley/dgx-spark-qwen3-coder-next-compose

This setup is aimed at a private VS Code coding-assistant workflow:
- Main model: Qwen/Qwen3-Coder-Next-FP8
- Autocomplete model: Qwen/Qwen2.5-Coder-3B
- Both exposed as local OpenAI-compatible endpoints
- Continue/Cline-oriented workflow

Why I think this may be useful:
- It is a tested DGX Spark result, not just a theoretical config
- The main model path that worked best here was a Spark-tuned vLLM build
- The repo documents context choices, memory headroom, and the autocomplete tradeoff between 3B and 7B

Interesting findings:
- Qwen3-Coder-Next-FP8 was stable at 32k context on this box
- 40k context was also feasible, but 32k was the better default
- Prefix caching gave a meaningful improvement on repeated long prompts
- Qwen2.5-Coder-7B autocomplete did fit under vLLM, but it was slower and not clearly better enough than 3B to become the default

Recent spot checks:
- Main coldish prompt: 7.97s
- Main repeated prompt with prefix caching: 2.37s
- Autocomplete short completion: 1.56s
- GPU memory: main model about 88.8 GiB
- GPU memory: autocomplete about 11.0 GiB with 3B

If this is helpful, I would be happy to compare notes with anyone else running large coding models on DGX Spark.
```

## Draft: Qwen Hugging Face Discussion

Suggested title:

`Tested DGX Spark setup for Qwen3-Coder-Next-FP8 with Continue/Cline`

Suggested post:

```text
I wanted to share a working DGX Spark deployment for Qwen/Qwen3-Coder-Next-FP8 aimed at a private coding-assistant workflow in VS Code.

Repo:
https://github.com/ztolley/dgx-spark-qwen3-coder-next-compose

Setup summary:
- Main assistant: Qwen/Qwen3-Coder-Next-FP8
- Autocomplete sidecar: Qwen/Qwen2.5-Coder-3B
- Backend: Spark-tuned vLLM path
- IDE workflow: Continue for chat/edit/apply + autocomplete, and Cline as an OpenAI-compatible agent client

Why I am posting it:
- It may help people trying to run Qwen3-Coder-Next privately on DGX Spark
- The repo includes practical context, memory, and performance observations
- It also documents what I tried that did not become the default

Current default:
- 32k context for the main model
- 4k context for autocomplete

Interesting findings:
- 40k context was feasible on this hardware, but 32k was the better default for daily use
- Qwen2.5-Coder-3B was a better default autocomplete tradeoff than 1.5B or 7B for this shared-box setup

If the Qwen team or other users have suggestions for an even better deployment path for Qwen3-Coder-Next on Spark-class hardware, I would love to compare notes.
```

## Draft: Continue Discussion

Suggested category:

- `Community Sharing` -> `Config`

Suggested title:

`DGX Spark local config: Qwen3-Coder-Next FP8 for chat/edit/apply + Qwen2.5-Coder-3B autocomplete`

Suggested post:

```text
I wanted to share a working local Continue setup for a DGX Spark private coding-assistant workflow.

Repo:
https://github.com/ztolley/dgx-spark-qwen3-coder-next-compose

Model split:
- Qwen/Qwen3-Coder-Next-FP8 for chat, edit, and apply
- Qwen/Qwen2.5-Coder-3B for autocomplete

Why this may be useful:
- It is a real tested setup on DGX Spark
- Both models are exposed as local OpenAI-compatible endpoints
- The repo includes a Continue config example and measured memory/performance notes

I also tested larger autocomplete options. 7B fit under vLLM, but 3B was the better default tradeoff for this box because it was faster and did not show a clear enough quality win to justify the extra memory.

If anyone else is running large local coding models with a separate autocomplete endpoint in Continue, I would be interested in comparing setups.
```

## Draft: Cline Community

Suggested places:

- Discord
- `r/cline`
- Feature request / feedback area if you want to frame it as a deployment report

Suggested post:

```text
I put together a tested DGX Spark setup for running Qwen/Qwen3-Coder-Next-FP8 locally as a private coding assistant for VS Code.

Repo:
https://github.com/ztolley/dgx-spark-qwen3-coder-next-compose

Highlights:
- Main agent model: Qwen/Qwen3-Coder-Next-FP8
- OpenAI-compatible local endpoint for Cline
- Separate local autocomplete sidecar kept online at the same time
- Real DGX Spark memory/context/performance notes in the repo docs

This may be useful for anyone trying to run a strong local coding model privately on unusual hardware instead of using a hosted API.
```

## Draft: Short Cross-Post

Use this for Discord, Reddit, or a short forum reply:

```text
Shared a tested DGX Spark setup for running Qwen3-Coder-Next-FP8 locally as a private VS Code coding assistant, with a separate Qwen2.5-Coder-3B autocomplete sidecar.

Repo:
https://github.com/ztolley/dgx-spark-qwen3-coder-next-compose

Includes:
- Docker Compose stack
- Continue and Cline setup notes
- persistent caches
- context/memory/performance notes
- 3B vs 7B autocomplete observations
```

## Posting Advice

- Lead with the problem it solves, not just the repo link.
- Mention that it is a tested result on real DGX Spark hardware.
- Be explicit that it is a community working reference, not an official vendor-supported recipe.
- Include one or two concrete numbers so the post feels real.
- Link both the repo and the technical notes page if the audience is highly technical.
