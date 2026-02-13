"""Tests for the 4 agent tools."""

import json
from pathlib import Path

import pytest


def _args(**kwargs: object) -> str:
    """Build a JSON args string for tool invocation."""
    return json.dumps(kwargs)


# -- Guard -----------------------------------------------------------------


class TestGuard:
    @pytest.mark.parametrize(
        "name",
        [".env", ".env.local", ".env.production", "server.pem", "id_rsa.key"],
    )
    def test_blocks_sensitive_names(self, name: str):
        from src.tools.guard import check_path

        assert check_path(name) is not None
        assert "Skipped" in check_path(name)

    def test_blocks_sensitive_dirs(self):
        from src.tools.guard import check_path

        assert check_path("/home/user/.ssh/id_rsa") is not None

    def test_blocks_config_gcloud(self):
        from src.tools.guard import check_path

        assert check_path("/home/user/.config/gcloud/credentials.json") is not None

    @pytest.mark.parametrize("name", ["readme.md", "src/config.py", ".env.example"])
    def test_allows_normal_files(self, name: str):
        from src.tools.guard import check_path

        assert check_path(name) is None

    async def test_read_blocked(self, tmp_path: Path):
        from src.tools.read import read_tool

        env = tmp_path / ".env"
        env.write_text("SECRET=123")

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(env)))
        assert "Skipped" in result

    async def test_write_blocked(self, tmp_path: Path):
        from src.tools.write import write_tool

        result = await write_tool.on_invoke_tool(
            None, _args(file_path=str(tmp_path / ".env"), content="hack")
        )
        assert "Skipped" in result

    async def test_edit_blocked(self, tmp_path: Path):
        from src.tools.edit import edit_tool

        env = tmp_path / ".env"
        env.write_text("SECRET=123")

        result = await edit_tool.on_invoke_tool(
            None, _args(file_path=str(env), old_text="123", new_text="456")
        )
        assert "Skipped" in result


# -- Read ------------------------------------------------------------------


class TestReadTool:
    async def test_read_file(self, tmp_path: Path):
        from src.tools.read import read_tool

        f = tmp_path / "hello.txt"
        f.write_text("line1\nline2\nline3\n")

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(f)))

        assert "line1" in result
        assert "line2" in result
        assert "3" in result

    async def test_read_with_offset_limit(self, tmp_path: Path):
        from src.tools.read import read_tool

        f = tmp_path / "nums.txt"
        f.write_text("\n".join(f"line{i}" for i in range(1, 11)))

        result = await read_tool.on_invoke_tool(
            None, _args(file_path=str(f), offset=3, limit=2)
        )

        assert "line3" in result
        assert "line4" in result
        assert "line5" not in result

    async def test_read_nonexistent(self):
        from src.tools.read import read_tool

        result = await read_tool.on_invoke_tool(
            None, _args(file_path="/nonexistent/file.txt")
        )

        assert "Error" in result


# -- Write -----------------------------------------------------------------


class TestWriteTool:
    async def test_write_creates_file(self, tmp_path: Path):
        from src.tools.write import write_tool

        target = tmp_path / "subdir" / "out.txt"
        result = await write_tool.on_invoke_tool(
            None, _args(file_path=str(target), content="hello world")
        )

        assert target.read_text() == "hello world"
        assert "bytes" in result


# -- Edit ------------------------------------------------------------------


class TestEditTool:
    async def test_edit_replaces(self, tmp_path: Path):
        from src.tools.edit import edit_tool

        f = tmp_path / "code.py"
        f.write_text("foo = 1\nbar = 2\n")

        result = await edit_tool.on_invoke_tool(
            None, _args(file_path=str(f), old_text="foo = 1", new_text="foo = 42")
        )

        assert "Replaced" in result
        assert "foo = 42" in f.read_text()

    async def test_edit_not_found(self, tmp_path: Path):
        from src.tools.edit import edit_tool

        f = tmp_path / "code.py"
        f.write_text("foo = 1\n")

        result = await edit_tool.on_invoke_tool(
            None, _args(file_path=str(f), old_text="bar = 2", new_text="bar = 3")
        )

        assert "Error" in result
        assert "not found" in result


# -- Bash ------------------------------------------------------------------


class TestBashTool:
    async def test_bash_echo(self):
        from src.tools.bash import bash_tool

        result = await bash_tool.on_invoke_tool(None, _args(command="echo hello"))
        assert "hello" in result

    async def test_bash_timeout(self):
        from src.tools.bash import bash_tool

        result = await bash_tool.on_invoke_tool(
            None, _args(command="sleep 10", timeout=1)
        )
        assert "timed out" in result

    async def test_bash_stderr(self):
        from src.tools.bash import bash_tool

        result = await bash_tool.on_invoke_tool(None, _args(command="echo err >&2"))
        assert "err" in result
