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

    def test_empty_input(self):
        assert dispatch("") is None
