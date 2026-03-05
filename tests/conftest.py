"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_config(monkeypatch: pytest.MonkeyPatch):
    """Reset global config singleton between tests."""
    import src.config as config_module

    config_module._config = None

    # Clear env vars that could leak between tests
    for key in (
        "PROVIDER",
        "API_KEY",
        "MODEL",
        "BASE_URL",
        "TEMPERATURE",
        "MAX_TOKENS",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _clean_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Reset session singleton and redirect SESSIONS_DIR to tmp_path."""
    import src.context as context_module

    context_module._session = None
    monkeypatch.setattr(context_module, "SESSIONS_DIR", tmp_path / "sessions")
