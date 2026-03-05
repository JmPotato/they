# Agent Guidelines

**they** is a minimal terminal AI agent built with Python 3.14+ and the OpenAI Agents SDK (with LiteLLM extension). 6 tools — read, write, edit, bash, mark, recall — no plugins, no framework abstractions.

## Development

```bash
uv sync --extra dev          # setup (uv only, not pip)
cp .env.example .env         # fill in PROVIDER, API_KEY, MODEL
uv run they                  # run
uv run pytest                # test
uv run ruff check . && uv run ruff format --check .  # lint
```

## Conventions

- **Testing**: pytest with pytest-asyncio (`asyncio_mode = "auto"`). Third-party deprecation warnings are filtered via `filterwarnings` in pyproject.toml — add new filters there, not in test code.
- **Config**: All runtime configuration via `.env`. Never commit `.env`.
- **Commits**: Must include `Signed-off-by`. Use `git commit -s`.

## Design Rationale (non-obvious)

- `temperature` and `max_tokens` default to `None` (omitted from API calls) to avoid unsupported-parameter errors with certain providers.
- Pydantic `UserWarning` from litellm usage serialisation is suppressed at the streaming scope in `loop.py` — this is a known upstream compatibility issue, not a bug.
- `guard.py` checks both the given filename and the symlink-resolved name — a plain name check alone can be bypassed via symlinks to sensitive files.

## Working with the Code

- Always read a file before editing it.
- Keep changes minimal — avoid unnecessary refactoring.
- Run tests and lint before committing.
- This file should stay concise — only record information that cannot be obtained by scanning the directory structure or reading the source code (e.g. non-obvious design rationale, workflow conventions, gotchas).
