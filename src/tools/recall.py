"""Recall tool — browse session history and marks."""

from agents import function_tool

from src.context import get_session


@function_tool
def recall_tool(action: str = "list", mark_index: int = -1, query: str = "") -> str:
    """Recall earlier context from session history.

    Args:
        action: "list" to show all marks, "entries" to show raw entries
                for a given mark range, "search" to search all entries.
        mark_index: For action="entries", which mark range to show.
                    -1 = entries before the first mark,
                    0 = entries after mark 0, etc.
        query: For action="search", the search term.
    """
    session = get_session()

    if action == "list":
        return session.format_marks_overview()

    if action == "entries":
        items = session.get_entries_between_marks(mark_index)
        if not items:
            return f"No entries found for mark_index={mark_index}."
        return session.format_entries(items)

    if action == "search":
        if not query:
            return "Please provide a query string for search."
        results = session.search_entries(query)
        return session.format_search_results(results)

    return f"Unknown action: {action!r}. Use 'list', 'entries', or 'search'."
