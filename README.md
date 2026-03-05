# they

Just yet another AI agent — they live in your terminal, read and write files, run shell commands. Nothing you haven't seen before.

## What They Do

They can read, write, edit files, run bash commands, and manage their own context. 6 tools, no plugins, no framework-of-the-week. Pick any LLM provider you like via LiteLLM, point them at your terminal, and start talking.

## Quick Start

Requires **Python 3.14+** and [uv](https://docs.astral.sh/uv/).

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
| `TEMPERATURE` | No       | Sampling temperature (omitted if not set)               |
| `MAX_TOKENS`  | No       | Max output tokens (omitted if not set)                  |

## Tools

Nothing fancy:

| Tool     | Description                                               |
| -------- | --------------------------------------------------------- |
| `read`   | Read file contents, with optional line range              |
| `write`  | Write content to a file, auto-creating parent directories |
| `edit`   | Find-and-replace (exact first match) in a file            |
| `bash`   | Execute shell commands with timeout and output truncation |
| `mark`   | Checkpoint a conversation phase with an optional summary  |
| `recall` | Browse session history, view entries, or search all history |

Inspired by [pi](https://pi.dev).

## Slash Commands

| Command      | Description                         |
| ------------ | ----------------------------------- |
| `/help`      | Show available commands             |
| `/model`     | Display current model configuration |
| `/mark`      | Summarise and checkpoint context    |
| `/sessions`  | List recent sessions                |
| `/resume N`  | Resume session N from list          |
| `/clear`     | Reset conversation history          |
| `/quit`      | Exit (alias: `/exit`)               |

## Keyboard Shortcuts

| Shortcut  | Description                                  |
| --------- | -------------------------------------------- |
| `Esc Esc` | Interrupt the current streaming operation    |

## License

[MIT](LICENSE)
