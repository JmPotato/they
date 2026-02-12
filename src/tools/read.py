"""Read file tool — read file contents with optional line range."""

from pathlib import Path

from agents import function_tool

from .guard import check_path


@function_tool
def read_tool(file_path: str, offset: int = 0, limit: int = 0) -> str:
    """Read a file and return its contents with line numbers.

    Args:
        file_path: Absolute or relative path to the file.
        offset: Start reading from this line number (1-based). 0 means from the beginning.
        limit: Maximum number of lines to read. 0 means read all.
    """
    if err := check_path(file_path):
        return err

    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"
    if not p.is_file():
        return f"Error: not a file: {file_path}"

    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    total = len(lines)

    start = max(0, offset - 1) if offset > 0 else 0
    end = start + limit if limit > 0 else total
    selected = lines[start:end]

    numbered = []
    for i, line in enumerate(selected, start=start + 1):
        numbered.append(f"{i:>6}\t{line.rstrip()}")

    header = f"[{p.name}] lines {start + 1}-{start + len(selected)} of {total}"
    return header + "\n" + "\n".join(numbered)
