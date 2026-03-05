"""Tests for console formatting helpers (pure logic functions only)."""

import json

import pytest

from src.tui.console import (
    _extract_api_message,
    _shorten_msg,
    _summarize_args,
    _walk_exception_chain,
    console,
    print_error,
    print_tool_call,
)


# -- print_tool_call ----------------------------------------------------------


class TestPrintToolCall:
    def test_with_known_key(self):
        with console.capture() as capture:
            print_tool_call("bash_tool", json.dumps({"command": "ls -la"}))
        output = capture.get()
        assert "bash_tool" in output
        assert "ls -la" in output

    def test_fallback_raw_args(self):
        raw = "x" * 200
        with console.capture() as capture:
            print_tool_call("some_tool", raw)
        output = capture.get()
        assert "some_tool" in output
        assert "…" in output
        assert len(output) < 300

    def test_no_args(self):
        with console.capture() as capture:
            print_tool_call("my_tool", "")
        output = capture.get()
        assert "my_tool" in output


# -- _summarize_args ----------------------------------------------------------


class TestSummarizeArgs:
    @pytest.mark.parametrize(
        "key,val",
        [("command", "ls -la"), ("file_path", "/tmp/foo.py"), ("path", "/tmp/bar")],
    )
    def test_extracts_known_keys(self, key: str, val: str):
        assert _summarize_args(json.dumps({key: val})) == val

    def test_priority_command_over_file_path(self):
        """When multiple keys exist, 'command' wins (first in priority list)."""
        args = json.dumps({"file_path": "/tmp/foo", "command": "ls"})
        assert _summarize_args(args) == "ls"

    def test_no_matching_key_returns_empty(self):
        assert _summarize_args(json.dumps({"other": "val"})) == ""

    @pytest.mark.parametrize("bad", ["not json", "", "42", "null"])
    def test_invalid_input_returns_empty(self, bad: str):
        assert _summarize_args(bad) == ""


# -- _shorten_msg -------------------------------------------------------------


class TestShortenMsg:
    def test_strips_litellm_prefix(self):
        msg = "litellm.ServiceUnavailableError: actual message"
        assert _shorten_msg(msg) == "actual message"

    def test_strips_chained_prefixes(self):
        msg = "litellm.ServiceUnavailableError: APIConnectionError: real error"
        assert _shorten_msg(msg) == "real error"

    def test_truncates_at_noise_marker(self):
        msg = "Something failed. Received Chunk=abc123"
        result = _shorten_msg(msg)
        assert "Received Chunk" not in result
        assert "Something failed" in result

    def test_truncates_at_original_exception_marker(self):
        msg = "Error occurred. Original exception: SomeError details"
        result = _shorten_msg(msg)
        assert "Original exception" not in result
        assert "Error occurred" in result

    def test_multiline_takes_first_line(self):
        assert _shorten_msg("first\nsecond\nthird") == "first"

    def test_plain_message_unchanged(self):
        assert _shorten_msg("simple error") == "simple error"


# -- _extract_api_message -----------------------------------------------------


class TestExtractApiMessage:
    def test_extracts_error_message(self):
        text = 'prefix {"error": {"message": "Rate limit exceeded"}} suffix'
        assert _extract_api_message(text) == "Rate limit exceeded"

    def test_returns_none_without_json(self):
        assert _extract_api_message("plain error text") is None

    def test_returns_none_when_error_not_dict(self):
        assert _extract_api_message('{"error": "string"}') is None

    def test_returns_none_for_malformed_json(self):
        assert _extract_api_message("{broken") is None

    def test_returns_none_when_error_dict_missing_message_key(self):
        assert _extract_api_message('{"error": {"code": 429}}') is None


# -- _walk_exception_chain ----------------------------------------------------


class TestWalkExceptionChain:
    def test_single_exception(self):
        exc = ValueError("solo")
        assert _walk_exception_chain(exc) == [exc]

    def test_follows_cause_chain(self):
        root = ConnectionError("timeout")
        wrapper = RuntimeError("request failed")
        wrapper.__cause__ = root

        chain = _walk_exception_chain(wrapper)

        assert len(chain) == 2
        assert chain[0] is wrapper
        assert chain[1] is root

    def test_circular_chain_terminates(self):
        a = ValueError("a")
        b = ValueError("b")
        a.__cause__ = b
        b.__cause__ = a

        chain = _walk_exception_chain(a)
        assert len(chain) == 2


# -- print_error --------------------------------------------------------------


def _capture_error(exc: Exception | str) -> str:
    """Call print_error and return the captured console output."""
    with console.capture() as capture:
        print_error(exc)
    return capture.get()


class TestPrintError:
    def test_string_error(self):
        output = _capture_error("something broke")
        assert "something broke" in output

    def test_exception_with_api_message(self):
        exc = RuntimeError('{"error": {"message": "Rate limit exceeded"}}')
        output = _capture_error(exc)
        assert "Rate limit exceeded" in output

    def test_chained_exception_shows_root_cause(self):
        root = ConnectionError("timeout")
        wrapper = RuntimeError("request failed")
        wrapper.__cause__ = root
        output = _capture_error(wrapper)
        assert "ConnectionError" in output

    def test_exception_without_api_message(self):
        exc = ValueError("plain failure")
        output = _capture_error(exc)
        assert "plain failure" in output

    def test_chained_exception_skips_root_when_repeats_api_msg(self):
        root = ConnectionError('{"error": {"message": "Rate limit exceeded"}}')
        wrapper = RuntimeError("request failed")
        wrapper.__cause__ = root
        output = _capture_error(wrapper)
        assert "Rate limit exceeded" in output
        # Root cause line should be suppressed since it repeats the API message
        assert "ConnectionError" not in output

    def test_tool_use_hint(self):
        output = _capture_error(RuntimeError("finish_reason: error"))
        assert "tool" in output.lower()
