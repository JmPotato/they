# they

Just yet another AI agent — they live in your terminal, read and write files, run shell commands. Nothing you haven't seen before.

## What They Do

They can read, write, edit files and run bash commands. That's all they do. 4 tools, no plugins, no framework-of-the-week. Pick any LLM provider you like via LiteLLM, point them at your terminal, and start talking.

## Quick Start

```bash
uv sync
cp .env.example .env
# Fill in your provider, API key, and model
uv run they
```

## Configuration

| Variable      | Required | Description                                             |
| ------------- | -------- | ------------------------------------------------------- |
| `PROVIDER`    | Yes      | LLM provider (`openrouter`, `anthropic`, `openai`, ...) |
| `API_KEY`     | Yes      | API key for the provider                                |
| `MODEL`       | Yes      | Model identifier (e.g. `moonshotai/kimi-k2.5`)          |
| `BASE_URL`    | No       | Custom endpoint URL                                     |
| `TEMPERATURE` | No       | Sampling temperature (default: `0.7`)                   |
| `MAX_TOKENS`  | No       | Max output tokens (default: `16384`)                    |

## Tools

Nothing fancy:

| Tool    | Description                                               |
| ------- | --------------------------------------------------------- |
| `read`  | Read file contents, with optional line range              |
| `write` | Write content to a file, auto-creating parent directories |
| `edit`  | Find-and-replace (exact first match) in a file            |
| `bash`  | Execute shell commands with timeout and output truncation |

Inspired by [pi](https://pi.dev).

## Slash Commands

| Command  | Description                         |
| -------- | ----------------------------------- |
| `/help`  | Show available commands             |
| `/model` | Display current model configuration |
| `/clear` | Reset conversation history          |
| `/quit`  | Exit                                |

## License

[MIT](LICENSE)
