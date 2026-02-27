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

    if p.is_dir():
        entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        lines = []
        for entry in entries:
            name = entry.name + ("/" if entry.is_dir() else "")
            lines.append(f"  {name}")
        header = f"[{p.name}/] {len(entries)} entries"
        return header + "\n" + "\n".join(lines) if lines else header

    if not p.is_file():
        return f"Error: not a regular file: {file_path}"

    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError, ValueError:
        return f"Error: not a text file (binary content): {file_path}"
    lines = text.splitlines(keepends=True)
    total = len(lines)

    if total == 0:
        return f"[{p.name}] (empty file)"

    start = max(0, offset - 1) if offset > 0 else 0
    end = start + limit if limit > 0 else total
    selected = lines[start:end]

    numbered = []
    for i, line in enumerate(selected, start=start + 1):
        numbered.append(f"{i:>6}\t{line.rstrip()}")

    header = f"[{p.name}] lines {start + 1}-{start + len(selected)} of {total}"
    return header + "\n" + "\n".join(numbered)
