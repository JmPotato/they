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

from src.context import (
    SessionLog,
    init_session,
    list_sessions,
    reset_session,
    resume_session,
)

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


async def _run_turn(agent: Agent, input_items: list) -> list | None:
    """Execute one agent turn with streaming.

    Returns the full ``result.to_input_list()`` on success, or ``None``
    if the user interrupted the stream.  The caller is responsible for
    computing new items (by slicing) and extending the session log.
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
        console.print("[dim](interrupted)[/dim]")
        full_result = None
    else:
        full_result = result.to_input_list()
    if in_tok or out_tok:
        print_usage(in_tok, out_tok)
    return full_result


async def _handle_user_mark(session: SessionLog) -> None:
    """Generate a summary via LLM and place a context mark."""
    entries = session.entries_since_last_mark()
    if not entries:
        console.print("[dim]Nothing to mark — no entries since last mark.[/dim]")
        return

    formatted = SessionLog.format_entries(entries)

    from litellm import acompletion

    from src.config import get_config

    cfg = get_config()
    try:
        response = await acompletion(
            model=cfg.litellm_model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarise the following conversation entries "
                        "concisely. Capture: key decisions, files modified, "
                        "outcomes, and current state. Be brief but complete."
                    ),
                },
                {"role": "user", "content": formatted},
            ],
        )
        summary = response.choices[0].message.content
    except Exception as e:
        print_error(e)
        return

    mark = session.add_mark(summary)
    console.print(
        f"[dim]Mark placed at position {mark.index} ({len(session.marks)} total).[/dim]"
    )


def _handle_resume(text: str) -> SessionLog | None:
    """Parse ``/resume N`` and load the corresponding session.

    Returns the loaded ``SessionLog`` on success, or ``None`` on error.
    """
    parts = text.strip().split()
    if len(parts) < 2:
        console.print("[dim]Usage: /resume N (use /sessions to see list)[/dim]")
        return None

    try:
        index = int(parts[1])
    except ValueError:
        console.print(f"[dim]Invalid index: {parts[1]}[/dim]")
        return None

    sessions = list_sessions()
    if not sessions:
        console.print("[dim]No saved sessions.[/dim]")
        return None

    if index < 0 or index >= len(sessions):
        console.print(f"[dim]Index {index} out of range (0–{len(sessions) - 1}).[/dim]")
        return None

    path = sessions[index]["path"]
    session = resume_session(path)
    console.print(
        f"[dim]Resumed session: {path.name} "
        f"({len(session.entries)} entries, {len(session.marks)} marks)[/dim]"
    )
    return session


async def run_loop(agent: Agent) -> None:
    """Top-level REPL: read user input → dispatch → execute agent turn.

    Uses a ``SessionLog`` to maintain an append-only history with
    mark-based context windowing.  The model sees a sliding window
    starting from the most recent mark's summary.
    """
    print_welcome()

    session = init_session()

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
        if stripped.startswith("/"):
            cmd = stripped.strip().lower().split()[0]

            if cmd == "/mark":
                await _handle_user_mark(session)
                continue

            signal = dispatch(stripped)
            if signal is Signal.QUIT:
                break
            if signal is Signal.CLEAR:
                session = reset_session()
                continue
            if signal is Signal.RESUME:
                loaded = _handle_resume(stripped)
                if loaded is not None:
                    session = loaded
            continue

        # -- Agent turn -------------------------------------------------------
        # Append user message to session log, build windowed input, run turn.
        user_msg = {"role": "user", "content": stripped}
        session.append(user_msg)
        input_items = session.build_input()

        try:
            full_result = await _run_turn(agent, input_items)
            if full_result is not None:
                new_items = full_result[len(input_items) :]
                session.extend(new_items)
        except KeyboardInterrupt:
            console.print("\n[dim](interrupted)[/dim]")
        except Exception as e:
            print_error(e)
