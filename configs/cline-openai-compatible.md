# Cline OpenAI-Compatible Setup

Cline's documentation currently describes provider setup through the settings UI rather than a stable plain-text config file. Use these values in the Cline settings panel for this Spark deployment:

- API Provider: `OpenAI Compatible`
- Base URL: `http://127.0.0.1:30000/v1`
- API Key: `local`
- Model ID: `Qwen/Qwen3-Coder-Next-FP8`
- Context Window: `32768`

Recommended notes:

- Use Cline for the main coding/agent workflow.
- Use Continue for inline autocomplete, pointed at the separate autocomplete endpoint.
- If you want to configure the Cline CLI instead of the VS Code extension, the equivalent command is:

```bash
cline auth -p openai -k local -b http://127.0.0.1:30000/v1 -m Qwen/Qwen3-Coder-Next-FP8
```
