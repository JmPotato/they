# Agent Guidelines

## Project Overview

**they** is a minimal terminal AI agent built with Python 3.14+ and the OpenAI Agents SDK (with LiteLLM extension). It provides 4 tools — read, write, edit, bash — and supports any LLM provider via LiteLLM.

## Architecture

```
main.py              — Entry point, configures LiteLLM and launches the TUI loop
src/
  config.py          — Config dataclass, loaded from .env via python-dotenv
  agent.py           — Agent creation (system prompt, model, tools)
  tools/             — Tool implementations (read, write, edit, bash)
    guard.py         — Path validation / safety guards
  tui/               — Terminal UI (prompt_toolkit input, Rich console output, slash commands)
tests/               — pytest + pytest-asyncio test suite
```

## Development

### Setup

```bash
uv sync
cp .env.example .env   # fill in PROVIDER, API_KEY, MODEL
```

### Run

```bash
uv run they
```

### Test

```bash
uv run pytest
```

### Lint

```bash
uv run ruff check .
uv run ruff format --check .
```

## Conventions

- **Package manager**: uv (not pip). Use `uv sync` / `uv run`.
- **Python version**: 3.14+.
- **Style**: Ruff for linting and formatting. No custom rules beyond defaults in pyproject.toml.
- **Testing**: pytest with pytest-asyncio (`asyncio_mode = "auto"`). Tests live in `tests/`.
- **Config**: All runtime configuration via environment variables / `.env` file. Never commit `.env`.
- **Dependencies**: Declared in `pyproject.toml` under `[project.dependencies]` and `[project.optional-dependencies.dev]`.

## Key Design Decisions

- **4 tools only**: read, write, edit, bash. No plugins, no framework abstractions.
- **LiteLLM for multi-provider support**: The provider/model pair is passed as `{provider}/{model}` to LiteLLM.
- **Tracing disabled**: Agent SDK tracing is turned off by default.
- **Frozen config**: `Config` is an immutable dataclass, loaded once as a singleton.

## Working with the Code

- Always read a file before editing it.
- Keep changes minimal and focused — avoid unnecessary refactoring.
- Run `uv run pytest` to verify changes before committing.
- Run `uv run ruff check . && uv run ruff format --check .` to ensure code style compliance.
