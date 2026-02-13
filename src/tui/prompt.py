"""Enhanced prompt input using prompt_toolkit."""

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

PASTE_THRESHOLD = 5
PASTE_MARKER = "[Pasted {} lines]"

_pasted_content: str | None = None

bindings = KeyBindings()


@bindings.add(Keys.BracketedPaste)
def _handle_paste(event):
    global _pasted_content
    data = event.data.replace("\r\n", "\n").replace("\r", "\n")
    lines = data.splitlines()
    if len(lines) > PASTE_THRESHOLD:
        _pasted_content = data
        event.current_buffer.insert_text(PASTE_MARKER.format(len(lines)))
    else:
        _pasted_content = None
        event.current_buffer.insert_text(data)


session = PromptSession(key_bindings=bindings)


async def prompt_input() -> str:
    """Read user input, returning full pasted content when paste was collapsed."""
    global _pasted_content
    _pasted_content = None

    text = await session.prompt_async(ANSI("\033[1;32m> \033[0m"))

    if _pasted_content is not None:
        result = text.replace(
            PASTE_MARKER.format(len(_pasted_content.splitlines())),
            _pasted_content,
        )
        _pasted_content = None
        return result
    return text
