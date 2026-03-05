"""Session log with mark-based context windowing.

Maintains an append-only log of all conversation items and supports
"marks" — checkpoints that summarise accumulated context so the model
always sees a sliding window starting from the most recent mark.

Sessions are persisted to ``~/.they/sessions/`` as JSON files, with
atomic writes on every mutation.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".they" / "sessions"


def _serialize_entry(item: object) -> object:
    """Convert an entry to a JSON-serializable form."""
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return item


@dataclass
class Mark:
    """A checkpoint in the session log.

    Attributes:
        index: Position in the log where the mark was placed.
        summary: LLM-generated summary of entries up to this point.
    """

    index: int
    summary: str = ""


@dataclass
class SessionLog:
    """Append-only session log with mark-based windowing."""

    entries: list = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    _store_path: Path | None = field(default=None, repr=False, compare=False)
    _created_at: str = field(default="", repr=False, compare=False)

    # -- Persistence ----------------------------------------------------------

    def _persist(self) -> None:
        """Atomic-write session state to disk (if a store path is set)."""
        if self._store_path is None:
            return
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "created_at": self._created_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "marks": [{"index": m.index, "summary": m.summary} for m in self.marks],
            "entries": [_serialize_entry(e) for e in self.entries],
        }
        tmp = self._store_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, self._store_path)

    @classmethod
    def _create_persisted(cls) -> SessionLog:
        """Create a new persisted session with a timestamped filename.

        The file is NOT written to disk here — it will be created lazily
        on the first mutation (append/extend/add_mark) to avoid polluting
        the sessions directory with empty files.
        """
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y-%m-%dT%H-%M-%S")
        short_id = uuid.uuid4().hex[:4]
        path = SESSIONS_DIR / f"{stamp}_{short_id}.json"
        return cls(
            _store_path=path,
            _created_at=now.isoformat(),
        )

    @classmethod
    def _load_from_file(cls, path: Path) -> SessionLog:
        """Deserialize a session from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        marks = [Mark(index=m["index"], summary=m["summary"]) for m in data["marks"]]
        session = cls(
            entries=data["entries"],
            marks=marks,
            _store_path=path,
            _created_at=data.get("created_at", ""),
        )
        return session

    # -- Mutators -------------------------------------------------------------

    def append(self, item: object) -> None:
        """Append a single entry to the log."""
        self.entries.append(item)
        self._persist()

    def extend(self, items: list) -> None:
        """Append multiple entries to the log."""
        self.entries.extend(items)
        self._persist()

    def add_mark(self, summary: str) -> Mark:
        """Place a mark at the current end of the log."""
        mark = Mark(index=len(self.entries), summary=summary)
        self.marks.append(mark)
        self._persist()
        return mark

    # -- Queries --------------------------------------------------------------

    def build_input(self) -> list:
        """Build the input list for the model.

        If no marks exist, returns all entries.  Otherwise returns
        entries after the last mark.  If the last mark has a summary,
        a clearly-labeled context header is prepended.
        """
        if not self.marks:
            return list(self.entries)

        last = self.marks[-1]
        tail = list(self.entries[last.index :])

        # Pure anchor — no summary, no injection
        if not last.summary:
            return tail

        # Summary exists — inject as clearly-labeled context header
        summary_pair: list = [
            {
                "role": "user",
                "content": (
                    f"[Context summary — {last.index} prior entries compressed]\n\n"
                    + last.summary
                ),
            },
            {"role": "assistant", "content": "Understood."},
        ]
        return summary_pair + tail

    def entries_since_last_mark(self) -> list:
        """Return entries from the last mark (or start) to the end."""
        start = self.marks[-1].index if self.marks else 0
        return list(self.entries[start:])

    def entry_count_since_last_mark(self) -> int:
        """Count entries since the last mark (or from start)."""
        start = self.marks[-1].index if self.marks else 0
        return len(self.entries) - start

    def get_entries_between_marks(self, mark_index: int) -> list:
        """Return entries for a given mark range.

        ``mark_index=-1`` returns entries before the first mark.
        ``mark_index=0`` returns entries between the first and second
        mark (or to end if only one mark), etc.
        """
        if mark_index < -1 or mark_index >= len(self.marks):
            return []

        if mark_index == -1:
            end = self.marks[0].index if self.marks else len(self.entries)
            return list(self.entries[:end])

        start = self.marks[mark_index].index
        if mark_index + 1 < len(self.marks):
            end = self.marks[mark_index + 1].index
        else:
            end = len(self.entries)
        return list(self.entries[start:end])

    def search_entries(self, query: str, max_results: int = 10) -> list[dict]:
        """Search all entries for a case-insensitive substring match.

        Returns a list of dicts with ``index``, ``mark_label``, and
        ``preview`` keys, ordered most-recent-first.
        """
        query_lower = query.lower()
        results: list[dict] = []
        for i in range(len(self.entries) - 1, -1, -1):
            if len(results) >= max_results:
                break
            entry = self.entries[i]
            text = ""
            if isinstance(entry, dict):
                content = entry.get("content", "")
                text = content if isinstance(content, str) else str(content)
            else:
                text = str(entry)
            if query_lower in text.lower():
                preview = text[:200] + "…" if len(text) > 200 else text
                results.append(
                    {
                        "index": i,
                        "mark_label": self._mark_label_for_index(i),
                        "preview": preview,
                    }
                )
        return results

    def format_search_results(self, results: list[dict]) -> str:
        """Format search results as human-readable text."""
        if not results:
            return "No matching entries found."
        lines: list[str] = []
        for r in results:
            lines.append(f"[entry {r['index']}] ({r['mark_label']}) {r['preview']}")
        return "\n".join(lines)

    def _mark_label_for_index(self, entry_index: int) -> str:
        """Return a human-readable label for which mark region an entry belongs to."""
        if not self.marks:
            return "no marks"
        if entry_index < self.marks[0].index:
            return "before mark 0"
        for i in range(len(self.marks) - 1):
            if entry_index < self.marks[i + 1].index:
                return f"between marks {i}\u2013{i + 1}"
        return f"after mark {len(self.marks) - 1}"

    # -- Formatting -----------------------------------------------------------

    def format_marks_overview(self) -> str:
        """Human-readable list of all marks."""
        if not self.marks:
            return "No marks placed yet."
        lines: list[str] = []
        for i, mark in enumerate(self.marks):
            if mark.summary:
                truncated = (
                    mark.summary[:120] + "…"
                    if len(mark.summary) > 120
                    else mark.summary
                )
                lines.append(f"[{i}] position {mark.index}: {truncated}")
            else:
                lines.append(f"[{i}] position {mark.index}: (pure anchor)")
        return "\n".join(lines)

    @staticmethod
    def format_entries(items: list) -> str:
        """Render a list of entries as human-readable text."""
        if not items:
            return "(no entries)"
        lines: list[str] = []
        for item in items:
            if isinstance(item, dict):
                role = item.get("role", "?")
                content = item.get("content", "")
                if isinstance(content, str):
                    preview = content[:200] + "…" if len(content) > 200 else content
                else:
                    preview = str(content)[:200]
                lines.append(f"[{role}] {preview}")
            else:
                lines.append(str(item)[:200])
        return "\n".join(lines)


# -- Module-level singleton ---------------------------------------------------

_session: SessionLog | None = None


def init_session() -> SessionLog:
    """Create a fresh persisted session log (start of conversation)."""
    global _session  # noqa: PLW0603
    _session = SessionLog._create_persisted()
    return _session


def reset_session() -> SessionLog:
    """Reset the session log (``/clear``)."""
    return init_session()


def get_session() -> SessionLog:
    """Access the current session log.

    Raises ``RuntimeError`` if no session has been initialised.
    """
    if _session is None:
        raise RuntimeError("No active session — call init_session() first.")
    return _session


def _extract_preview(entries: list, max_len: int = 80) -> str:
    """Return the first user message content, truncated for display."""
    for entry in entries:
        if isinstance(entry, dict) and entry.get("role") == "user":
            content = entry.get("content", "")
            if isinstance(content, str):
                text = content.replace("\n", " ").strip()
                if len(text) > max_len:
                    return text[:max_len] + "…"
                return text
    return ""


def list_sessions(limit: int = 20) -> list[dict]:
    """List recent sessions, newest first.

    Returns a list of dicts with keys: ``path``, ``created_at``, ``updated_at``,
    ``entry_count``, ``mark_count``, ``preview``.  Sessions with no entries
    are excluded.
    """
    if not SESSIONS_DIR.exists():
        return []
    files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.name, reverse=True)
    results: list[dict] = []
    for path in files:
        if len(results) >= limit:
            break
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError, OSError:
            continue
        entries = data.get("entries", [])
        if not entries:
            continue
        results.append(
            {
                "path": path,
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "entry_count": len(entries),
                "mark_count": len(data.get("marks", [])),
                "preview": _extract_preview(entries),
            }
        )
    return results


def resume_session(path: Path) -> SessionLog:
    """Load a session from file and set it as the active singleton."""
    global _session  # noqa: PLW0603
    _session = SessionLog._load_from_file(path)
    return _session
