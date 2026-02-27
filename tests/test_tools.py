"""Tests for the 4 agent tools."""

import json
import os
from pathlib import Path

import pytest

from src.tools.bash import bash_tool
from src.tools.edit import edit_tool
from src.tools.guard import check_path
from src.tools.read import read_tool
from src.tools.write import write_tool


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
        assert check_path(name) is not None
        assert "Skipped" in check_path(name)

    def test_blocks_sensitive_dirs(self):
        assert check_path("/home/user/.ssh/id_rsa") is not None

    def test_blocks_config_gcloud(self):
        assert check_path("/home/user/.config/gcloud/credentials.json") is not None

    def test_blocks_symlink_to_sensitive_file(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("SECRET=123")
        link = tmp_path / "harmless.txt"
        link.symlink_to(env)
        assert check_path(str(link)) is not None

    @pytest.mark.parametrize("name", ["readme.md", "src/config.py", ".env.example"])
    def test_allows_normal_files(self, name: str):
        assert check_path(name) is None

    async def test_read_blocked(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("SECRET=123")

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(env)))
        assert "Skipped" in result

    async def test_write_blocked(self, tmp_path: Path):
        result = await write_tool.on_invoke_tool(
            None, _args(file_path=str(tmp_path / ".env"), content="hack")
        )
        assert "Skipped" in result

    async def test_edit_blocked(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("SECRET=123")

        result = await edit_tool.on_invoke_tool(
            None, _args(file_path=str(env), old_text="123", new_text="456")
        )
        assert "Skipped" in result


# -- Read ------------------------------------------------------------------


class TestReadTool:
    async def test_read_file(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        f.write_text("line1\nline2\nline3\n")

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(f)))

        assert "line1" in result
        assert "line2" in result
        assert "3" in result

    async def test_read_with_offset_limit(self, tmp_path: Path):
        f = tmp_path / "nums.txt"
        f.write_text("\n".join(f"line{i}" for i in range(1, 11)))

        result = await read_tool.on_invoke_tool(
            None, _args(file_path=str(f), offset=3, limit=2)
        )

        assert "line3" in result
        assert "line4" in result
        assert "line5" not in result

    async def test_read_directory(self, tmp_path: Path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file_a.txt").write_text("a")
        (tmp_path / "file_b.py").write_text("b")

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(tmp_path)))

        assert "3 entries" in result
        assert "subdir/" in result
        assert "file_a.txt" in result
        assert "file_b.py" in result

    async def test_read_empty_directory(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(empty)))

        assert "0 entries" in result

    async def test_read_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.txt"
        f.write_text("")

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(f)))

        assert "empty file" in result

    async def test_read_binary_file(self, tmp_path: Path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x80\xff" * 100)

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(f)))

        assert "not a text file" in result

    async def test_read_special_file(self, tmp_path: Path):
        fifo = tmp_path / "test_fifo"
        os.mkfifo(fifo)

        result = await read_tool.on_invoke_tool(None, _args(file_path=str(fifo)))

        assert "not a regular file" in result

    async def test_read_nonexistent(self):
        result = await read_tool.on_invoke_tool(
            None, _args(file_path="/nonexistent/file.txt")
        )

        assert "Error" in result


# -- Write -----------------------------------------------------------------


class TestWriteTool:
    async def test_write_creates_file(self, tmp_path: Path):
        target = tmp_path / "subdir" / "out.txt"
        result = await write_tool.on_invoke_tool(
            None, _args(file_path=str(target), content="hello world")
        )

        assert target.read_text() == "hello world"
        assert "characters" in result

    async def test_write_overwrites_existing(self, tmp_path: Path):
        target = tmp_path / "file.txt"
        target.write_text("old content")

        await write_tool.on_invoke_tool(
            None, _args(file_path=str(target), content="new content")
        )

        assert target.read_text() == "new content"


# -- Edit ------------------------------------------------------------------


class TestEditTool:
    async def test_edit_replaces(self, tmp_path: Path):
        f = tmp_path / "code.py"
        f.write_text("foo = 1\nbar = 2\n")

        result = await edit_tool.on_invoke_tool(
            None, _args(file_path=str(f), old_text="foo = 1", new_text="foo = 42")
        )

        assert "Replaced" in result
        assert "foo = 42" in f.read_text()

    async def test_edit_not_found(self, tmp_path: Path):
        f = tmp_path / "code.py"
        f.write_text("foo = 1\n")

        result = await edit_tool.on_invoke_tool(
            None, _args(file_path=str(f), old_text="bar = 2", new_text="bar = 3")
        )

        assert "Error" in result
        assert "not found" in result

    async def test_edit_identical_text(self, tmp_path: Path):
        f = tmp_path / "code.py"
        f.write_text("foo = 1\n")

        result = await edit_tool.on_invoke_tool(
            None, _args(file_path=str(f), old_text="foo = 1", new_text="foo = 1")
        )

        assert "identical" in result

    async def test_edit_replaces_first_occurrence_only(self, tmp_path: Path):
        f = tmp_path / "dup.txt"
        f.write_text("foo\nfoo\nfoo\n")

        await edit_tool.on_invoke_tool(
            None, _args(file_path=str(f), old_text="foo", new_text="bar")
        )

        assert f.read_text() == "bar\nfoo\nfoo\n"

    async def test_edit_nonexistent_file(self, tmp_path: Path):
        result = await edit_tool.on_invoke_tool(
            None,
            _args(file_path=str(tmp_path / "nope.py"), old_text="x", new_text="y"),
        )

        assert "Error" in result
        assert "file not found" in result


# -- Bash ------------------------------------------------------------------


class TestBashTool:
    async def test_bash_echo(self):
        result = await bash_tool.on_invoke_tool(None, _args(command="echo hello"))
        assert "hello" in result

    async def test_bash_timeout(self):
        result = await bash_tool.on_invoke_tool(
            None, _args(command="sleep 10", timeout=1)
        )
        assert "timed out" in result

    async def test_bash_stderr(self):
        result = await bash_tool.on_invoke_tool(None, _args(command="echo err >&2"))
        assert "err" in result

    async def test_bash_nonzero_exit_code(self):
        result = await bash_tool.on_invoke_tool(None, _args(command="exit 42"))
        assert "exit code: 42" in result

    async def test_bash_no_output(self):
        result = await bash_tool.on_invoke_tool(None, _args(command="true"))
        assert result == "(no output)"

    async def test_bash_truncates_large_output(self):
        result = await bash_tool.on_invoke_tool(
            None, _args(command="python3 -c \"print('x' * 50000)\"")
        )
        assert "truncated" in result
