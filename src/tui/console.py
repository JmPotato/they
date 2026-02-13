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
            "[bold]they[/bold] await. [dim]Esc×2 to interrupt · /help for commands[/dim]",
            border_style="blue",
        )
    )


def print_tool_call(name: str, args: str) -> None:
    """Show a brief one-line summary: tool name + key arg."""
    summary = _summarize_args(args)
    if not summary and args:
        # Fallback: show truncated raw args so tool calls are never opaque
        summary = args[:120] + ("…" if len(args) > 120 else "")
    label = f"  [{name}] {summary}" if summary else f"  [{name}]"
    console.print(Text(label, style="dim"))


def _summarize_args(args: str) -> str:
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


def _shorten_msg(msg: str) -> str:
    """Shorten a single error message line."""
    short = msg.split("\n")[0]
    short = _LITELLM_PREFIX_RE.sub("", short)
    for marker in _NOISE_MARKERS:
        idx = short.find(marker)
        if idx > 0:
            short = short[:idx].rstrip(" ,.")
    return short


def _extract_api_message(text: str) -> str | None:
    """Try to pull the human-readable message from a JSON API error body."""
    start = text.find("{")
    if start < 0:
        return None
    # Find the matching closing brace (handle nested braces)
    depth, end = 0, start
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError, ValueError:
        return None
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return data["error"].get("message")
    return None


def _walk_exception_chain(exc: BaseException) -> list[BaseException]:
    """Collect all exceptions from __cause__ / __context__ chain."""
    chain = [exc]
    seen = {id(exc)}
    current = exc
    while True:
        cause = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )
        if cause is None or id(cause) in seen:
            break
        seen.add(id(cause))
        chain.append(cause)
        current = cause
    return chain


def print_error(exc: Exception | str) -> None:
    if isinstance(exc, str):
        console.print(Text(f"Error: {_shorten_msg(exc)}", style="bold red"))
        return

    chain = _walk_exception_chain(exc)
    full_msg = str(exc)

    # Try to extract a clean API error from any exception in the chain
    api_msg = None
    for e in chain:
        api_msg = _extract_api_message(str(e))
        if api_msg:
            break

    if api_msg:
        console.print(Text(f"Error: {api_msg}", style="bold red"))
    else:
        console.print(Text(f"Error: {_shorten_msg(full_msg)}", style="bold red"))

    # Show the root cause type if the chain has depth (helps locate the real origin)
    if len(chain) > 1:
        root = chain[-1]
        root_type = type(root).__name__
        root_str = str(root).split("\n")[0][:200]
        # Skip if it just repeats the API message
        if not api_msg or api_msg not in root_str:
            console.print(Text(f"  ({root_type}: {root_str})", style="dim"))

    # Hint for models that don't support tool use
    lower = full_msg.lower()
    if "finish_reason: error" in lower or "abort" in lower:
        console.print(
            "[dim]Hint: your model may not support tool use. "
            "Try a tool-capable model (e.g. openrouter/anthropic/claude-sonnet-4-20250514)[/dim]"
        )
