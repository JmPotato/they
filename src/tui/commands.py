"""Slash commands — local handlers for /xxx inputs."""

from collections.abc import Callable
from enum import Enum

from .console import console


class Signal(Enum):
    """Control signals returned by dispatch() to the main loop."""

    QUIT = "quit"
    CLEAR = "clear"
    RESUME = "resume"


def handle_help() -> None:
    console.print(
        "[bold]Commands:[/bold]\n"
        "  /help      — show this message\n"
        "  /model     — show current model\n"
        "  /mark      — summarise and checkpoint context\n"
        "  /sessions  — list recent sessions\n"
        "  /resume N  — resume session N from list\n"
        "  /clear     — clear conversation history\n"
        "  /quit      — exit\n\n"
        "[bold]Shortcuts:[/bold]\n"
        "  Esc Esc — interrupt current operation"
    )


def handle_model() -> None:
    from src.config import get_config

    cfg = get_config()
    console.print(f"[bold]Provider:[/bold] {cfg.provider}")
    console.print(f"[bold]Model:[/bold] {cfg.model}")
    console.print(
        f"[dim]temperature={cfg.temperature}  max_tokens={cfg.max_tokens}[/dim]"
    )


def handle_sessions() -> None:
    from src.context import list_sessions

    sessions = list_sessions()
    if not sessions:
        console.print("[dim]No saved sessions.[/dim]")
        return
    for i, s in enumerate(sessions):
        created = s["created_at"][:19].replace("T", " ") if s["created_at"] else "?"
        console.print(
            f"  [bold]{i}[/bold]  {created}  "
            f"entries={s['entry_count']}  marks={s['mark_count']}"
        )
        preview = s.get("preview", "")
        if preview:
            console.print(f"       [dim]{preview}[/dim]")


# Return value: "quit" to exit, "clear" to reset history, None to continue
COMMANDS: dict[str, Callable[[], None]] = {
    "/help": handle_help,
    "/model": handle_model,
}

# Commands that need special loop control (not just print-and-continue)
QUIT_COMMANDS = frozenset({"/quit", "/exit"})
CLEAR_COMMANDS = frozenset({"/clear"})


def dispatch(text: str) -> Signal | None:
    """Handle a slash command. Returns a control signal or None."""
    parts = text.strip().lower().split()
    if not parts:
        return None
    cmd = parts[0]

    if cmd in QUIT_COMMANDS:
        console.print("Bye!")
        return Signal.QUIT

    if cmd in CLEAR_COMMANDS:
        console.print("[dim]Conversation cleared.[/dim]")
        return Signal.CLEAR

    if cmd == "/sessions":
        handle_sessions()
        return None

    if cmd == "/resume":
        return Signal.RESUME

    handler = COMMANDS.get(cmd)
    if handler:
        handler()
        return None

    console.print(
        f"[dim]Unknown command: {cmd}. Type /help for available commands.[/dim]"
    )
    return None
