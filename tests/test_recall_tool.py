"""Tests for the recall tool."""

import json

from src.context import init_session
from src.tools.recall import recall_tool


class TestRecallToolList:
    async def test_list_empty(self):
        init_session()
        result = await recall_tool.on_invoke_tool(None, json.dumps({"action": "list"}))
        assert "No marks" in result

    async def test_list_with_marks(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        session.add_mark("First mark summary")
        session.append({"role": "user", "content": "world"})
        session.add_mark("Second mark summary")

        result = await recall_tool.on_invoke_tool(None, json.dumps({"action": "list"}))
        assert "[0]" in result
        assert "[1]" in result
        assert "First mark" in result
        assert "Second mark" in result


class TestRecallToolEntries:
    async def test_entries_before_first_mark(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        session.append({"role": "assistant", "content": "hi"})
        session.add_mark("done")

        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "entries", "mark_index": -1})
        )
        assert "[user] hello" in result
        assert "[assistant] hi" in result

    async def test_entries_after_mark(self):
        session = init_session()
        session.append({"role": "user", "content": "old"})
        session.add_mark("phase 1")
        session.append({"role": "user", "content": "new"})

        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "entries", "mark_index": 0})
        )
        assert "[user] new" in result
        assert "old" not in result

    async def test_invalid_mark_index(self):
        init_session()
        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "entries", "mark_index": 99})
        )
        assert "No entries found" in result


class TestRecallToolEntriesDefault:
    async def test_entries_default_mark_index(self):
        """Default mark_index=-1 returns entries before the first mark."""
        session = init_session()
        session.append({"role": "user", "content": "before mark"})
        session.add_mark("done")
        session.append({"role": "user", "content": "after mark"})

        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "entries"})
        )
        assert "before mark" in result
        assert "after mark" not in result


class TestRecallToolSearch:
    async def test_search_basic(self):
        session = init_session()
        session.append({"role": "user", "content": "fix the login bug"})
        session.append({"role": "assistant", "content": "done"})
        session.append({"role": "user", "content": "now fix the logout bug"})

        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "search", "query": "bug"})
        )
        assert "login bug" in result
        assert "logout bug" in result

    async def test_search_no_query(self):
        init_session()
        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "search", "query": ""})
        )
        assert "provide a query" in result.lower()

    async def test_search_multiple_matches_order(self):
        session = init_session()
        session.append({"role": "user", "content": "first match"})
        session.append({"role": "assistant", "content": "no match here"})
        session.append({"role": "user", "content": "second match"})

        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "search", "query": "match"})
        )
        # Most recent first
        second_pos = result.find("second match")
        first_pos = result.find("first match")
        assert second_pos < first_pos

    async def test_search_no_results(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        result = await recall_tool.on_invoke_tool(
            None, json.dumps({"action": "search", "query": "zzz_nonexistent"})
        )
        assert "No matching" in result


class TestRecallToolUnknownAction:
    async def test_unknown_action(self):
        init_session()
        result = await recall_tool.on_invoke_tool(None, json.dumps({"action": "bogus"}))
        assert "Unknown action" in result
