"""Write file tool — write content to a file, creating directories as needed."""

from pathlib import Path

from agents import function_tool

from .guard import check_path


@function_tool
def write_tool(file_path: str, content: str) -> str:
    """Write content to a file. Parent directories are created automatically.

    Args:
        file_path: Absolute or relative path to the file.
        content: The full content to write.
    """
    if err := check_path(file_path):
        return err

    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    written = p.write_text(content, encoding="utf-8")
    return f"Wrote {written} bytes to {file_path}"
