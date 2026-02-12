"""Agent creation — LitellmModel + System Prompt + Tools."""

from agents import Agent, ModelSettings
from agents.extensions.models.litellm_model import LitellmModel

from .config import Config, get_config
from .tools import ALL_TOOLS

SYSTEM_PROMPT = """\
You are **they**, a direct and capable AI assistant operating in a terminal.

You have 4 tools:
- **read_tool**: Read file contents (supports line ranges)
- **write_tool**: Write content to files (auto-creates directories)
- **edit_tool**: Find-and-replace in files (first match only)
- **bash_tool**: Execute shell commands

Guidelines:
- Read before editing — always verify current content first.
- Be precise — use exact strings for edit_tool replacements.
- Be concise — give short, direct answers unless asked for detail.
- Show your work — when modifying files, explain what you changed and why.
"""


def create_agent(config: Config | None = None) -> Agent:
    """Create and return the configured Agent."""
    cfg = config or get_config()

    model = LitellmModel(
        model=cfg.litellm_model, api_key=cfg.api_key, base_url=cfg.base_url
    )
    settings = ModelSettings(
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )

    return Agent(
        name="they",
        instructions=SYSTEM_PROMPT,
        model=model,
        model_settings=settings,
        tools=ALL_TOOLS,
    )
