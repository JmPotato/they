"""Shared test fixtures."""

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
