"""Main conversation loop — streamed Agent execution."""

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


def _handle_event(event: RawResponsesStreamEvent | RunItemStreamEvent) -> None:
    """Dispatch a single stream event to the appropriate console printer."""
    if isinstance(event, RawResponsesStreamEvent):
        if isinstance(event.data, ResponseTextDeltaEvent):
            print_text_delta(event.data.delta)
        return

    if not isinstance(event, RunItemStreamEvent):
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
            user_input = console.input("[bold green]> [/bold green]")
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
            result = Runner.run_streamed(agent, input=input_items)
            async for event in result.stream_events():
                _handle_event(event)
            console.print()
            input_items = result.to_input_list()
        except KeyboardInterrupt:
            console.print("\n[dim](interrupted)[/dim]")
        except Exception as e:
            print_error(str(e))
