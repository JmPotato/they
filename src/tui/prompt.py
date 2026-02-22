"""Enhanced prompt input using prompt_toolkit."""

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

PASTE_THRESHOLD = 5
PASTE_MARKER = "[Pasted {} lines]"


class PasteAwarePrompt:
    """Prompt session that collapses large pastes into a placeholder."""

    def __init__(self) -> None:
        self._pasted_content: str | None = None
        self._bindings = KeyBindings()
        self._register_bindings()
        self._session = PromptSession(key_bindings=self._bindings)

    def _register_bindings(self) -> None:
        @self._bindings.add(Keys.BracketedPaste)
        def _handle_paste(event):
            data = event.data.replace("\r\n", "\n").replace("\r", "\n")
            lines = data.splitlines()
            if len(lines) > PASTE_THRESHOLD:
                self._pasted_content = data
                event.current_buffer.insert_text(PASTE_MARKER.format(len(lines)))
            else:
                self._pasted_content = None
                event.current_buffer.insert_text(data)

    async def prompt_input(self) -> str:
        """Read user input, returning full pasted content when paste was collapsed."""
        self._pasted_content = None

        text = await self._session.prompt_async(ANSI("\033[1;32m> \033[0m"))

        if self._pasted_content is not None:
            result = text.replace(
                PASTE_MARKER.format(len(self._pasted_content.splitlines())),
                self._pasted_content,
            )
            self._pasted_content = None
            return result
        return text


# Module-level instance for convenience
_prompt = PasteAwarePrompt()
prompt_input = _prompt.prompt_input
