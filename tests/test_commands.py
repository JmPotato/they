"""Tests for slash command dispatch."""

import pytest

from src.tui.commands import Signal, dispatch


class TestDispatch:
    @pytest.mark.parametrize("cmd", ["/quit", "/exit", "/QUIT", "/Exit"])
    def test_quit_variants(self, cmd: str):
        assert dispatch(cmd) is Signal.QUIT

    def test_clear(self):
        assert dispatch("/clear") is Signal.CLEAR

    @pytest.mark.parametrize("cmd", ["/help", "/model"])
    def test_handler_commands_return_none(
        self, cmd: str, monkeypatch: pytest.MonkeyPatch
    ):
        # /model calls get_config() internally
        monkeypatch.setenv("PROVIDER", "test")
        monkeypatch.setenv("API_KEY", "test")
        monkeypatch.setenv("MODEL", "test")
        assert dispatch(cmd) is None

    def test_unknown_command(self):
        assert dispatch("/nonexistent") is None

    def test_sessions_returns_none(self):
        assert dispatch("/sessions") is None

    def test_resume_returns_signal(self):
        assert dispatch("/resume 0") is Signal.RESUME

    def test_resume_without_argument(self):
        assert dispatch("/resume") is Signal.RESUME

    @pytest.mark.parametrize("cmd", ["  /quit  ", "  /exit  "])
    def test_whitespace_around_command(self, cmd: str):
        assert dispatch(cmd) is Signal.QUIT

    def test_empty_input(self):
        assert dispatch("") is None
