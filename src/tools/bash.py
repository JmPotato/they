"""Bash tool — execute shell commands asynchronously."""

import asyncio

from agents import function_tool

MAX_OUTPUT = 30000


@function_tool
async def bash_tool(command: str, timeout: int = 120) -> str:
    """Execute a shell command and return its output.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 120).
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return f"Error: command timed out after {timeout}s"

    parts: list[str] = []
    if stdout:
        out = stdout.decode(errors="replace")
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + "\n... (truncated)"
        parts.append(out)
    if stderr:
        err = stderr.decode(errors="replace")
        if len(err) > MAX_OUTPUT:
            err = err[:MAX_OUTPUT] + "\n... (truncated)"
        parts.append(f"[stderr]\n{err}")
    if proc.returncode != 0:
        parts.append(f"[exit code: {proc.returncode}]")

    return "\n".join(parts) if parts else "(no output)"
