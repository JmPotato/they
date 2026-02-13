"""Main conversation loop — streamed Agent execution."""

import asyncio
import os
import sys
import termios
import time
import tty
import warnings

from agents import Agent, Runner
from agents.items import ToolCallItem
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
from openai.types.responses import ResponseTextDeltaEvent

from .commands import dispatch
from .console import (
    console,
    print_error,
    print_text_delta,
    print_tool_call,
    print_welcome,
)
from .prompt import prompt_input

DOUBLE_ESC_WINDOW = 0.5  # seconds


class _EscMonitor:
    """Async context manager that detects double-Esc keypresses during streaming.

    Sets the terminal to cbreak mode so individual keypresses arrive immediately,
    then watches stdin via the event loop's reader.  Two Esc presses within
    ``DOUBLE_ESC_WINDOW`` seconds set the ``interrupted`` flag.
    """

    def __init__(self):
        self._last_esc: float = 0
        self._triggered = False
        self._fd = sys.stdin.fileno()
        self._old_settings: list | None = None

    # -- event-loop callback --------------------------------------------------

    def _on_readable(self):
        data = os.read(self._fd, 1024)
        if data == b"\x1b":
            now = time.monotonic()
            if now - self._last_esc < DOUBLE_ESC_WINDOW:
                self._triggered = True
            self._last_esc = now

    # -- context manager ------------------------------------------------------

    async def __aenter__(self):
        self._triggered = False
        self._last_esc = 0
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        asyncio.get_running_loop().add_reader(self._fd, self._on_readable)
        return self

    async def __aexit__(self, *exc):
        asyncio.get_running_loop().remove_reader(self._fd)
        if self._old_settings is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)

    @property
    def interrupted(self) -> bool:
        return self._triggered


def _handle_event(event: RawResponsesStreamEvent | RunItemStreamEvent) -> None:
    """Dispatch a single stream event to the appropriate console printer."""
    if isinstance(event, RawResponsesStreamEvent):
        if isinstance(event.data, ResponseTextDeltaEvent):
            print_text_delta(event.data.delta)
        return

    if not isinstance(event, RunItemStreamEvent):
        return

    if event.name != "tool_called":
        return

    item = event.item
    if isinstance(item, ToolCallItem) and item.raw_item:
        name = getattr(item.raw_item, "name", "") or ""
        args = getattr(item.raw_item, "arguments", "") or ""
        if name:
            console.print()
            print_tool_call(name, args)


async def run_loop(agent: Agent) -> None:
    """Run the interactive conversation loop."""
    print_welcome()

    input_items: list = []

    while True:
        console.print()
        try:
            user_input = await prompt_input()
        except EOFError, KeyboardInterrupt:
            console.print("\nBye!")
            break

        stripped = user_input.strip()
        if not stripped:
            continue

        # Slash commands are handled locally
        if stripped.startswith("/"):
            signal = dispatch(stripped)
            if signal == "quit":
                break
            if signal == "clear":
                input_items = []
            continue

        input_items.append({"role": "user", "content": stripped})

        try:
            # litellm returns `usage` as a plain dict while the Agents SDK
            # expects a ResponseAPIUsage Pydantic model, causing a harmless
            # UserWarning during serialisation.  Suppress it for the entire
            # streaming + serialisation scope (upstream compatibility issue).
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=UserWarning, module=r"pydantic\.main"
                )
                result = Runner.run_streamed(agent, input=input_items, max_turns=100)
                async with _EscMonitor() as esc:
                    async for event in result.stream_events():
                        if esc.interrupted:
                            break
                        _handle_event(event)
                console.print()
                if esc.interrupted:
                    console.print("[dim](interrupted)[/dim]")
                else:
                    input_items = result.to_input_list()
        except KeyboardInterrupt:
            console.print("\n[dim](interrupted)[/dim]")
        except Exception as e:
            print_error(e)
