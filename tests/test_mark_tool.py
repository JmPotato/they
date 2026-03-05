"""Tests for the mark tool."""

import json

from src.context import init_session
from src.tools.mark import mark_tool


class TestMarkTool:
    async def test_places_mark(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        session.append({"role": "assistant", "content": "hi"})

        result = await mark_tool.on_invoke_tool(
            None, json.dumps({"summary": "Greeted the user"})
        )
        assert "Mark placed" in result
        assert "position 2" in result
        assert len(session.marks) == 1
        assert session.marks[0].summary == "Greeted the user"

    async def test_multiple_marks(self):
        session = init_session()
        session.append({"role": "user", "content": "a"})
        await mark_tool.on_invoke_tool(None, json.dumps({"summary": "first"}))
        session.append({"role": "user", "content": "b"})
        await mark_tool.on_invoke_tool(None, json.dumps({"summary": "second"}))
        assert len(session.marks) == 2
        assert "3 total" in (
            await mark_tool.on_invoke_tool(None, json.dumps({"summary": "third"}))
        )

    async def test_mark_without_summary(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        result = await mark_tool.on_invoke_tool(None, json.dumps({}))
        assert "Mark placed" in result
        assert session.marks[0].summary == ""

    async def test_mark_empty_summary(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        result = await mark_tool.on_invoke_tool(None, json.dumps({"summary": ""}))
        assert "Mark placed" in result
        assert session.marks[0].summary == ""
