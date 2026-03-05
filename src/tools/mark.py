"""Mark tool — checkpoint a phase with an optional summary."""

from agents import function_tool

from src.context import get_session


@function_tool
def mark_tool(summary: str = "") -> str:
    """Place a context mark that checkpoints the current conversation phase.

    Args:
        summary: Optional summary of the conversation so far.
                 If omitted, places a pure anchor (context cutoff)
                 without injecting any summary.
    """
    session = get_session()
    mark = session.add_mark(summary)
    return f"Mark placed at position {mark.index} ({len(session.marks)} total marks)."
