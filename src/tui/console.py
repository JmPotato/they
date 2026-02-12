"""Rich Console formatting helpers."""

import json
import re

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# Regex to strip chained litellm exception prefixes like
# "litellm.ServiceUnavailableError: litellm.MidStreamFallbackError: ..."
_LITELLM_PREFIX_RE = re.compile(r"^(?:(?:litellm\.\w+Error|APIConnectionError): )+")

# Noise suffixes to truncate at
_NOISE_MARKERS = ("Received Chunk=", "Original exception:")


def print_welcome() -> None:
    console.print(
        Panel(
            "[bold]they[/bold] await. [dim]/quit to leave.[/dim]",
            border_style="blue",
        )
    )


def print_tool_call(name: str, args: str) -> None:
    """Show a brief one-line summary: tool name + key arg."""
    summary = _summarize_args(name, args)
    label = f"  [{name}] {summary}" if summary else f"  [{name}]"
    console.print(Text(label, style="dim"))


def _summarize_args(name: str, args: str) -> str:
    """Extract the most relevant arg value for a one-line display."""
    try:
        parsed = json.loads(args)
    except json.JSONDecodeError, TypeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    # Pick the most informative field per tool
    for key in ("command", "file_path", "path"):
        if key in parsed:
            return str(parsed[key])
    return ""


def print_text_delta(delta: str) -> None:
    console.print(delta, end="", highlight=False)


def print_error(msg: str) -> None:
    short = msg.split("\n")[0]
    short = _LITELLM_PREFIX_RE.sub("", short)
    for marker in _NOISE_MARKERS:
        idx = short.find(marker)
        if idx > 0:
            short = short[:idx].rstrip(" ,.")
    console.print(Text(f"Error: {short}", style="bold red"))

    # Hint for models that don't support tool use
    lower = msg.lower()
    if "finish_reason: error" in lower or "abort" in lower:
        console.print(
            "[dim]Hint: your model may not support tool use. "
            "Try a tool-capable model (e.g. openrouter/anthropic/claude-sonnet-4-20250514)[/dim]"
        )
