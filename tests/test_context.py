"""Tests for session log and mark-based context windowing."""

import json

import pytest
from pydantic import BaseModel

from src.context import (
    SESSIONS_DIR,
    Mark,
    SessionLog,
    _extract_preview,
    _serialize_entry,
    get_session,
    init_session,
    list_sessions,
    reset_session,
    resume_session,
)


class TestSessionLogAppendExtend:
    def test_append_single(self):
        log = SessionLog()
        log.append({"role": "user", "content": "hello"})
        assert len(log.entries) == 1
        assert log.entries[0]["content"] == "hello"

    def test_extend_multiple(self):
        log = SessionLog()
        log.extend(
            [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        )
        assert len(log.entries) == 2

    def test_append_preserves_order(self):
        log = SessionLog()
        for i in range(5):
            log.append({"role": "user", "content": str(i)})
        assert [e["content"] for e in log.entries] == ["0", "1", "2", "3", "4"]


class TestBuildInput:
    def test_no_marks_returns_all(self):
        log = SessionLog()
        log.extend(
            [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        )
        result = log.build_input()
        assert len(result) == 2
        assert result[0]["content"] == "a"

    def test_no_marks_returns_copy(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        result = log.build_input()
        result.append({"role": "user", "content": "extra"})
        assert len(log.entries) == 1

    def test_with_mark_returns_summary_plus_tail(self):
        log = SessionLog()
        log.extend(
            [
                {"role": "user", "content": "old1"},
                {"role": "assistant", "content": "old2"},
            ]
        )
        log.add_mark("Phase 1 summary")
        log.extend(
            [
                {"role": "user", "content": "new1"},
                {"role": "assistant", "content": "new2"},
            ]
        )
        result = log.build_input()
        # summary pair (2) + new entries (2) = 4
        assert len(result) == 4
        assert "Phase 1 summary" in result[0]["content"]
        assert "2 prior entries compressed" in result[0]["content"]
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Understood."
        assert result[2]["content"] == "new1"
        assert result[3]["content"] == "new2"

    def test_multiple_marks_uses_last(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        log.add_mark("mark 1")
        log.append({"role": "user", "content": "b"})
        log.add_mark("mark 2")
        log.append({"role": "user", "content": "c"})
        result = log.build_input()
        # summary pair (2) + entries after last mark (1)
        assert len(result) == 3
        assert "mark 2" in result[0]["content"]
        assert result[2]["content"] == "c"

    def test_mark_at_end_no_tail(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        log.add_mark("done")
        result = log.build_input()
        # summary pair only, no entries after mark
        assert len(result) == 2
        assert "done" in result[0]["content"]


class TestAddMark:
    def test_mark_index_at_current_length(self):
        log = SessionLog()
        log.extend([{"role": "user", "content": str(i)} for i in range(3)])
        mark = log.add_mark("summary")
        assert mark.index == 3
        assert mark.summary == "summary"

    def test_multiple_marks(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        m1 = log.add_mark("first")
        log.append({"role": "user", "content": "b"})
        m2 = log.add_mark("second")
        assert len(log.marks) == 2
        assert m1.index == 1
        assert m2.index == 2

    def test_mark_is_dataclass(self):
        mark = Mark(index=5, summary="test")
        assert mark.index == 5
        assert mark.summary == "test"


class TestEntriesSinceLastMark:
    def test_no_marks(self):
        log = SessionLog()
        log.extend([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])
        assert len(log.entries_since_last_mark()) == 2

    def test_with_mark(self):
        log = SessionLog()
        log.append({"role": "user", "content": "old"})
        log.add_mark("summary")
        log.append({"role": "user", "content": "new"})
        result = log.entries_since_last_mark()
        assert len(result) == 1
        assert result[0]["content"] == "new"

    def test_empty_after_mark(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        log.add_mark("summary")
        assert log.entries_since_last_mark() == []


class TestEntryCountSinceLastMark:
    def test_no_marks(self):
        log = SessionLog()
        log.extend([{"role": "user", "content": "a"}] * 5)
        assert log.entry_count_since_last_mark() == 5

    def test_with_mark(self):
        log = SessionLog()
        log.extend([{"role": "user", "content": "a"}] * 3)
        log.add_mark("summary")
        log.extend([{"role": "user", "content": "b"}] * 2)
        assert log.entry_count_since_last_mark() == 2


class TestGetEntriesBetweenMarks:
    def test_before_first_mark(self):
        log = SessionLog()
        log.extend([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])
        log.add_mark("m1")
        log.append({"role": "user", "content": "c"})
        result = log.get_entries_between_marks(-1)
        assert len(result) == 2

    def test_after_mark(self):
        log = SessionLog()
        log.append({"role": "user", "content": "before"})
        log.add_mark("m1")
        log.extend([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])
        log.add_mark("m2")
        result = log.get_entries_between_marks(0)
        assert len(result) == 2
        assert result[0]["content"] == "a"

    def test_last_mark_to_end(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        log.add_mark("m1")
        log.extend([{"role": "user", "content": "b"}, {"role": "user", "content": "c"}])
        result = log.get_entries_between_marks(0)
        assert len(result) == 2

    def test_invalid_index(self):
        log = SessionLog()
        assert log.get_entries_between_marks(0) == []
        assert log.get_entries_between_marks(-2) == []
        log.add_mark("m1")
        assert log.get_entries_between_marks(1) == []

    def test_no_marks_before_first(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        result = log.get_entries_between_marks(-1)
        assert len(result) == 1


class TestFormatMarksOverview:
    def test_no_marks(self):
        log = SessionLog()
        assert log.format_marks_overview() == "No marks placed yet."

    def test_with_marks(self):
        log = SessionLog()
        log.extend([{"role": "user", "content": "a"}] * 3)
        log.add_mark("First phase done")
        log.extend([{"role": "user", "content": "b"}] * 2)
        log.add_mark("Second phase done")
        overview = log.format_marks_overview()
        assert "[0]" in overview
        assert "[1]" in overview
        assert "First phase done" in overview
        assert "Second phase done" in overview

    def test_long_summary_truncated(self):
        log = SessionLog()
        log.add_mark("x" * 200)
        overview = log.format_marks_overview()
        assert "…" in overview


class TestFormatEntries:
    def test_empty(self):
        assert SessionLog.format_entries([]) == "(no entries)"

    def test_dict_entries(self):
        items = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = SessionLog.format_entries(items)
        assert "[user] hello" in result
        assert "[assistant] hi there" in result

    def test_non_dict_entries(self):
        result = SessionLog.format_entries(["raw string item"])
        assert "raw string item" in result

    def test_long_content_truncated(self):
        items = [{"role": "user", "content": "x" * 300}]
        result = SessionLog.format_entries(items)
        assert "…" in result

    def test_non_string_content_in_dict(self):
        items = [{"role": "user", "content": ["list", "of", "things"]}]
        result = SessionLog.format_entries(items)
        assert "[user]" in result
        # Non-string content goes through str()[:200]
        assert "list" in result


class TestSessionSingleton:
    def test_init_session(self):
        session = init_session()
        assert isinstance(session, SessionLog)
        assert session is get_session()

    def test_reset_session(self):
        s1 = init_session()
        s1.append({"role": "user", "content": "old"})
        s2 = reset_session()
        assert s2 is not s1
        assert len(s2.entries) == 0
        assert s2 is get_session()

    def test_get_session_without_init(self):
        with pytest.raises(RuntimeError, match="No active session"):
            get_session()


class TestPersistence:
    def test_init_defers_file_creation(self):
        session = init_session()
        assert session._store_path is not None
        assert not session._store_path.exists()
        session.append({"role": "user", "content": "hello"})
        assert session._store_path.exists()

    def test_append_persists(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        data = json.loads(session._store_path.read_text())
        assert len(data["entries"]) == 1
        assert data["entries"][0]["content"] == "hello"

    def test_extend_persists(self):
        session = init_session()
        session.extend(
            [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        )
        data = json.loads(session._store_path.read_text())
        assert len(data["entries"]) == 2

    def test_add_mark_persists(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        session.add_mark("checkpoint")
        data = json.loads(session._store_path.read_text())
        assert len(data["marks"]) == 1
        assert data["marks"][0]["summary"] == "checkpoint"

    def test_file_contains_metadata(self):
        session = init_session()
        session.append({"role": "user", "content": "test"})
        data = json.loads(session._store_path.read_text())
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] != ""
        assert data["updated_at"] != ""

    def test_in_memory_session_writes_nothing(self):
        """SessionLog() without _store_path doesn't write files."""
        session = SessionLog()
        session.append({"role": "user", "content": "hello"})
        session.add_mark("test")
        assert session._store_path is None


class TestSessionListAndResume:
    def test_empty_dir_returns_empty(self):
        assert list_sessions() == []

    def test_session_listable_after_mutation(self):
        session = init_session()
        assert list_sessions() == []
        session.append({"role": "user", "content": "hello world"})
        sessions = list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["entry_count"] == 1
        assert sessions[0]["preview"] == "hello world"

    def test_resume_loads_entries_and_marks(self):
        session = init_session()
        session.append({"role": "user", "content": "hello"})
        session.add_mark("phase 1")
        path = session._store_path

        # Reset the singleton
        import src.context as ctx

        ctx._session = None

        loaded = resume_session(path)
        assert len(loaded.entries) == 1
        assert loaded.entries[0]["content"] == "hello"
        assert len(loaded.marks) == 1
        assert loaded.marks[0].summary == "phase 1"
        assert loaded is get_session()

    def test_resumed_session_continues_persisting(self):
        session = init_session()
        session.append({"role": "user", "content": "old"})
        path = session._store_path

        import src.context as ctx

        ctx._session = None

        loaded = resume_session(path)
        loaded.append({"role": "user", "content": "new"})

        data = json.loads(path.read_text())
        assert len(data["entries"]) == 2
        assert data["entries"][1]["content"] == "new"


class TestListSessionsPreview:
    def test_preview_from_first_user_message(self):
        session = init_session()
        session.extend(
            [
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "Fix the login bug"},
                {"role": "user", "content": "Also refactor auth"},
            ]
        )
        sessions = list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["preview"] == "Fix the login bug"

    def test_preview_truncated(self):
        session = init_session()
        long_msg = "a" * 100
        session.append({"role": "user", "content": long_msg})
        sessions = list_sessions()
        assert sessions[0]["preview"] == "a" * 80 + "…"

    def test_preview_newlines_replaced(self):
        session = init_session()
        session.append({"role": "user", "content": "line one\nline two\nline three"})
        sessions = list_sessions()
        assert sessions[0]["preview"] == "line one line two line three"

    def test_empty_sessions_excluded(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        empty_file = SESSIONS_DIR / "2026-01-01T00-00-00_dead.json"
        empty_file.write_text(
            json.dumps(
                {"created_at": "", "updated_at": "", "marks": [], "entries": []}
            ),
            encoding="utf-8",
        )
        assert list_sessions() == []

    def test_preview_empty_when_no_user_entry(self):
        session = init_session()
        session.append({"role": "assistant", "content": "I can help!"})
        sessions = list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["preview"] == ""

    def test_corrupt_json_file_skipped(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        corrupt = SESSIONS_DIR / "2026-01-01T00-00-00_baad.json"
        corrupt.write_text("not valid json {{{", encoding="utf-8")
        # Should not raise and should return empty (no valid sessions)
        assert list_sessions() == []

    def test_list_sessions_limit(self):
        for i in range(5):
            session = init_session()
            session.append({"role": "user", "content": f"session {i}"})
        results = list_sessions(limit=3)
        assert len(results) == 3


class TestExtractPreview:
    def test_basic(self):
        assert _extract_preview([{"role": "user", "content": "hello"}]) == "hello"

    def test_empty_list(self):
        assert _extract_preview([]) == ""

    def test_non_string_content(self):
        assert _extract_preview([{"role": "user", "content": 42}]) == ""

    def test_custom_max_len(self):
        entries = [{"role": "user", "content": "a" * 50}]
        result = _extract_preview(entries, max_len=20)
        assert result == "a" * 20 + "…"

    def test_short_max_len_no_truncation(self):
        entries = [{"role": "user", "content": "hi"}]
        assert _extract_preview(entries, max_len=10) == "hi"


class TestBuildInputPureAnchor:
    def test_build_input_empty_summary_pure_anchor(self):
        """Empty-summary mark acts as pure anchor — no summary pair injected."""
        log = SessionLog()
        log.extend(
            [
                {"role": "user", "content": "old"},
                {"role": "assistant", "content": "old reply"},
            ]
        )
        log.add_mark("")
        log.extend(
            [
                {"role": "user", "content": "new"},
                {"role": "assistant", "content": "new reply"},
            ]
        )
        result = log.build_input()
        # Only the tail entries — no summary pair
        assert len(result) == 2
        assert result[0]["content"] == "new"
        assert result[1]["content"] == "new reply"

    def test_build_input_summary_format(self):
        """Summary injection uses the new clearly-labeled format."""
        log = SessionLog()
        for i in range(5):
            log.append({"role": "user", "content": f"msg{i}"})
        log.add_mark("Summary text here")
        log.append({"role": "user", "content": "after"})
        result = log.build_input()
        header = result[0]["content"]
        assert header.startswith("[Context summary — 5 prior entries compressed]")
        assert "Summary text here" in header
        assert result[1]["content"] == "Understood."


class TestSearchEntries:
    def test_search_entries_basic(self):
        log = SessionLog()
        log.append({"role": "user", "content": "hello world"})
        log.append({"role": "assistant", "content": "greetings"})
        log.append({"role": "user", "content": "goodbye world"})
        results = log.search_entries("world")
        assert len(results) == 2
        # Most recent first
        assert results[0]["index"] == 2
        assert results[1]["index"] == 0

    def test_search_entries_case_insensitive(self):
        log = SessionLog()
        log.append({"role": "user", "content": "Hello World"})
        results = log.search_entries("hello world")
        assert len(results) == 1
        assert results[0]["index"] == 0

    def test_search_entries_reverse_order(self):
        log = SessionLog()
        for i in range(5):
            log.append({"role": "user", "content": f"item {i}"})
        results = log.search_entries("item")
        assert [r["index"] for r in results] == [4, 3, 2, 1, 0]

    def test_search_entries_max_results(self):
        log = SessionLog()
        for i in range(20):
            log.append({"role": "user", "content": f"match {i}"})
        results = log.search_entries("match", max_results=5)
        assert len(results) == 5

    def test_search_entries_no_match(self):
        log = SessionLog()
        log.append({"role": "user", "content": "hello"})
        results = log.search_entries("zzz_no_match")
        assert results == []

    def test_search_entries_with_marks(self):
        log = SessionLog()
        log.append({"role": "user", "content": "alpha"})
        log.add_mark("mark 0")
        log.append({"role": "user", "content": "beta alpha"})
        log.add_mark("mark 1")
        log.append({"role": "user", "content": "gamma alpha"})
        results = log.search_entries("alpha")
        assert len(results) == 3
        assert results[0]["mark_label"] == "after mark 1"
        assert results[1]["mark_label"] == "between marks 0\u20131"
        assert results[2]["mark_label"] == "before mark 0"


class TestFormatSearchResults:
    def test_format_empty(self):
        log = SessionLog()
        assert log.format_search_results([]) == "No matching entries found."

    def test_format_results(self):
        log = SessionLog()
        results = [
            {"index": 3, "mark_label": "after mark 0", "preview": "some text"},
        ]
        formatted = log.format_search_results(results)
        assert "[entry 3]" in formatted
        assert "(after mark 0)" in formatted
        assert "some text" in formatted


class TestMarkLabelForIndex:
    def test_no_marks(self):
        log = SessionLog()
        assert log._mark_label_for_index(0) == "no marks"

    def test_before_first_mark(self):
        log = SessionLog()
        log.extend([{"role": "user", "content": str(i)} for i in range(3)])
        log.add_mark("m0")
        assert log._mark_label_for_index(0) == "before mark 0"
        assert log._mark_label_for_index(2) == "before mark 0"

    def test_between_marks(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        log.add_mark("m0")
        log.append({"role": "user", "content": "b"})
        log.add_mark("m1")
        log.append({"role": "user", "content": "c"})
        assert log._mark_label_for_index(1) == "between marks 0\u20131"

    def test_after_last_mark(self):
        log = SessionLog()
        log.append({"role": "user", "content": "a"})
        log.add_mark("m0")
        log.append({"role": "user", "content": "b"})
        assert log._mark_label_for_index(1) == "after mark 0"


class TestSerializeEntry:
    def test_dict_passthrough(self):
        d = {"role": "user", "content": "hello"}
        assert _serialize_entry(d) is d

    def test_pydantic_model_dump(self):
        class Msg(BaseModel):
            role: str
            content: str

        msg = Msg(role="user", content="hi")
        result = _serialize_entry(msg)
        assert isinstance(result, dict)
        assert result == {"role": "user", "content": "hi"}
