"""Edit file tool — find-and-replace in a file."""

from pathlib import Path

from agents import function_tool

from .guard import check_path


@function_tool
def edit_tool(file_path: str, old_text: str, new_text: str) -> str:
    """Replace the first occurrence of old_text with new_text in a file.

    Args:
        file_path: Path to the file to edit.
        old_text: The exact text to find (first match only).
        new_text: The replacement text.
    """
    if err := check_path(file_path):
        return err

    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"

    content = p.read_text(encoding="utf-8")
    if old_text not in content:
        return (
            f"Error: old_text not found in {file_path}. "
            "Use read_tool to verify the current file contents."
        )

    new_content = content.replace(old_text, new_text, 1)
    p.write_text(new_content, encoding="utf-8")
    return f"Replaced 1 occurrence in {file_path}"
