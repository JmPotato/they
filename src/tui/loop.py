"""Main conversation loop — streamed Agent execution."""

import asyncio
import os
import sys
import time
import warnings

try:
    import termios
    import tty

    _HAS_TERMIOS = True
except ImportError:  # Windows
    _HAS_TERMIOS = False

from agents import Agent, Runner
from agents.items import ToolCallItem
from agents.result import RunResultStreaming
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
from openai.types.responses import ResponseCompletedEvent, ResponseTextDeltaEvent
from rich.live import Live
from rich.markdown import Markdown

from .commands import Signal, dispatch
from .console import console, print_error, print_tool_call, print_usage, print_welcome
from .prompt import prompt_input


async def _stream_response(result: RunResultStreaming) -> tuple[bool, int, int]:
    """Consume the streaming response from the Agent, rendering output live.

    This function handles three concerns in a single pass over the event stream:

    1. **Markdown rendering** — text deltas are accumulated and fed into a
       Rich ``Live`` display that re-renders the full Markdown on each chunk,
       giving the user a progressively-updating formatted view.

    2. **Double-Esc interrupt** — while streaming, stdin is switched to cbreak
       mode so individual keypresses arrive immediately.  A reader callback
       watches for two consecutive Esc presses within 0.5 s and sets a flag
       that breaks out of the event loop on the next iteration.

    3. **Token tracking** — when the provider sends a ``ResponseCompletedEvent``
       (end of a model response), we extract ``input_tokens`` / ``output_tokens``
       from the usage payload for display after the turn.

    Returns:
        ``(interrupted, input_tokens, output_tokens)``
    """
    text_buf: list[str] = []
    input_tokens = 0
    output_tokens = 0
    interrupted = False
    live: Live | None = None

    # -- Set up double-Esc detection -----------------------------------------
    # Switch stdin to cbreak mode so we receive each keypress individually
    # (normally the terminal buffers until Enter).  Register a reader callback
    # on the event loop that fires whenever stdin has data.  Two Esc presses
    # (0x1b) within 0.5 s set `interrupted = True`.
    last_esc = 0.0
    fd = sys.stdin.fileno()
    old_settings = None

    def _on_stdin():
        nonlocal last_esc, interrupted
        data = os.read(fd, 1024)
        if data == b"\x1b":
            now = time.monotonic()
            if now - last_esc < 0.5:
                interrupted = True
            last_esc = now

    if _HAS_TERMIOS:
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        asyncio.get_running_loop().add_reader(fd, _on_stdin)

    try:
        async for event in result.stream_events():
            if interrupted:
                break

            # -- Handle raw model responses -----------------------------------
            # The SDK emits two kinds of raw events we care about:
            #   • ResponseTextDeltaEvent  — a chunk of generated text
            #   • ResponseCompletedEvent  — end-of-response with usage stats
            if isinstance(event, RawResponsesStreamEvent):
                data = event.data
                if isinstance(data, ResponseTextDeltaEvent):
                    # Accumulate text and update the Live Markdown display.
                    # Live is created lazily on the first delta so we don't
                    # show an empty panel during pure tool-call sequences.
                    text_buf.append(data.delta)
                    if live is None:
                        live = Live(
                            Markdown(""),
                            console=console,
                            vertical_overflow="visible",
                        )
                        live.start()
                    live.update(Markdown("".join(text_buf)))
                elif isinstance(data, ResponseCompletedEvent):
                    # Accumulate token counts across all responses in this turn
                    # (multi-step tool-use turns produce multiple responses).
                    usage = getattr(data.response, "usage", None)
                    if usage:
                        input_tokens += getattr(usage, "input_tokens", 0) or 0
                        output_tokens += getattr(usage, "output_tokens", 0) or 0
                continue

            # -- Handle tool calls --------------------------------------------
            # When the agent invokes a tool, we:
            #   1. Stop the Live display so rendered text stays on screen
            #   2. Print a dim one-liner showing the tool name + key argument
            #   3. Clear the text buffer — the next text segment (after the
            #      tool returns) gets its own fresh Live display
            if not isinstance(event, RunItemStreamEvent):
                continue
            if event.name != "tool_called":
                continue
            item = event.item
            if isinstance(item, ToolCallItem) and item.raw_item:
                name = getattr(item.raw_item, "name", "") or ""
                args = getattr(item.raw_item, "arguments", "") or ""
                if name:
                    if live is not None:
                        live.stop()
                        live = None
                    console.print()
                    print_tool_call(name, args)
                    text_buf.clear()
    finally:
        # -- Tear down --------------------------------------------------------
        # Always clean up, even if the stream raised an exception:
        #   • Stop Live so partial Markdown doesn't hang on screen
        #   • Remove the stdin reader and restore original terminal settings
        if live is not None:
            live.stop()
        if _HAS_TERMIOS:
            asyncio.get_running_loop().remove_reader(fd)
            if old_settings is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return interrupted, input_tokens, output_tokens


async def _run_turn(agent: Agent, input_items: list) -> list:
    """Execute one agent turn with streaming and return updated history.

    Orchestrates a single request → stream → result cycle:
      1. Suppress a harmless LiteLLM/Pydantic serialisation warning
      2. Kick off ``Runner.run_streamed`` (non-blocking — returns immediately)
      3. Await ``_stream_response`` which consumes the event stream, renders
         output, and returns interrupt / token-usage info
      4. If the user didn't interrupt, snapshot the full conversation
         (``result.to_input_list()``) so the next turn has complete context
      5. Display token usage if the provider reported it
    """
    with warnings.catch_warnings():
        # litellm returns `usage` as a plain dict while the Agents SDK expects
        # a ResponseAPIUsage Pydantic model → harmless UserWarning on
        # serialisation.  Safe to suppress for the entire streaming scope.
        warnings.filterwarnings(
            "ignore", category=UserWarning, module=r"pydantic\.main"
        )
        result = Runner.run_streamed(agent, input=input_items, max_turns=100)
        interrupted, in_tok, out_tok = await _stream_response(result)

    console.print()
    if interrupted:
        # User double-Esc'd — keep the existing input_items unchanged so the
        # partial response is discarded and the user can retry or continue.
        console.print("[dim](interrupted)[/dim]")
    else:
        # Successful completion — replace input_items with the full
        # conversation history (user messages + assistant responses + tool
        # results) so the next turn has complete context.
        input_items = result.to_input_list()
    if in_tok or out_tok:
        print_usage(in_tok, out_tok)
    return input_items


async def run_loop(agent: Agent) -> None:
    """Top-level REPL: read user input → dispatch → execute agent turn.

    ``input_items`` is the rolling conversation history passed to the Agent
    on each turn.  It grows with each successful turn (via
    ``result.to_input_list()``) and resets on ``/clear``.
    """
    print_welcome()

    input_items: list = []

    while True:
        console.print()  # blank line between turns for visual separation

        # -- Read input -------------------------------------------------------
        # prompt_input() uses prompt_toolkit with bracketed-paste support.
        # Ctrl-D (EOFError) and Ctrl-C (KeyboardInterrupt) exit the loop.
        try:
            user_input = await prompt_input()
        except EOFError, KeyboardInterrupt:
            console.print("\nBye!")
            break

        stripped = user_input.strip()
        if not stripped:
            continue

        # -- Slash commands ---------------------------------------------------
        # Handled locally without touching the Agent.  dispatch() returns a
        # control signal: "quit" / "clear" / None (command handled, continue).
        if stripped.startswith("/"):
            signal = dispatch(stripped)
            if signal is Signal.QUIT:
                break
            if signal is Signal.CLEAR:
                input_items = []
            continue

        # -- Agent turn -------------------------------------------------------
        # Append the user message to history, then run the Agent.  _run_turn
        # returns the (possibly updated) input_items list.  If it raises, we
        # show an error and leave input_items as-is so the user can retry.
        input_items.append({"role": "user", "content": stripped})

        try:
            input_items = await _run_turn(agent, input_items)
        except KeyboardInterrupt:
            console.print("\n[dim](interrupted)[/dim]")
        except Exception as e:
            print_error(e)
