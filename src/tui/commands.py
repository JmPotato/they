"""Slash commands — local handlers for /xxx inputs."""

from .console import console


def handle_help() -> None:
    console.print(
        "[bold]Commands:[/bold]\n"
        "  /help   — show this message\n"
        "  /model  — show current model\n"
        "  /clear  — clear conversation history\n"
        "  /quit   — exit"
    )


def handle_model() -> None:
    from src.config import get_config

    cfg = get_config()
    console.print(f"[bold]Provider:[/bold] {cfg.provider}")
    console.print(f"[bold]Model:[/bold] {cfg.model}")
    console.print(
        f"[dim]temperature={cfg.temperature}  max_tokens={cfg.max_tokens}[/dim]"
    )


# Return value: "quit" to exit, "clear" to reset history, None to continue
COMMANDS: dict[str, callable] = {
    "/help": handle_help,
    "/model": handle_model,
}

# Commands that need special loop control (not just print-and-continue)
QUIT_COMMANDS = frozenset({"/quit", "/exit"})
CLEAR_COMMANDS = frozenset({"/clear"})


def dispatch(text: str) -> str | None:
    """Handle a slash command. Returns a control signal or None.

    Returns:
        "quit"  — caller should exit the loop
        "clear" — caller should reset conversation history
        None    — command handled, continue normally
    """
    cmd = text.lower().split()[0]

    if cmd in QUIT_COMMANDS:
        console.print("Bye!")
        return "quit"

    if cmd in CLEAR_COMMANDS:
        console.print("[dim]Conversation cleared.[/dim]")
        return "clear"

    handler = COMMANDS.get(cmd)
    if handler:
        handler()
        return None

    console.print(
        f"[dim]Unknown command: {cmd}. Type /help for available commands.[/dim]"
    )
    return None
