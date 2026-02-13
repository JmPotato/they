"""Tests for configuration module."""

from pathlib import Path

import pytest

from src.config import Config, get_config


class TestConfig:
    def test_from_env_loads_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "PROVIDER=anthropic\n"
            "API_KEY=sk-test\n"
            "MODEL=claude-sonnet-4-20250514\n"
            "TEMPERATURE=0.5\n"
            "MAX_TOKENS=8192\n"
        )

        config = Config.from_env(env_file)
        assert config.provider == "anthropic"
        assert config.api_key == "sk-test"
        assert config.model == "claude-sonnet-4-20250514"
        assert config.temperature == 0.5
        assert config.max_tokens == 8192

    def test_from_env_defaults(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("PROVIDER=openrouter\nAPI_KEY=sk-test\nMODEL=test/model\n")

        config = Config.from_env(env_file)
        assert config.temperature is None
        assert config.max_tokens is None
        assert config.base_url is None

    def test_from_env_with_base_url(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "PROVIDER=openai\n"
            "API_KEY=sk-test\n"
            "MODEL=gpt-4o\n"
            "BASE_URL=https://custom.example.com/v1\n"
        )

        config = Config.from_env(env_file)
        assert config.base_url == "https://custom.example.com/v1"

    def test_from_env_missing_model_raises(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("PROVIDER=openrouter\nAPI_KEY=sk-test\n")

        with pytest.raises(ValueError, match="MODEL required"):
            Config.from_env(env_file)

    def test_from_env_missing_provider_raises(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=sk-test\nMODEL=test/model\n")

        with pytest.raises(ValueError, match="PROVIDER"):
            Config.from_env(env_file)

    def test_from_env_missing_api_key_raises(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("PROVIDER=openrouter\nMODEL=test/model\n")

        with pytest.raises(ValueError, match="API_KEY"):
            Config.from_env(env_file)

    def test_litellm_model_property(self):
        config = Config(
            provider="openrouter",
            api_key="sk-test",
            model="anthropic/claude-sonnet-4-20250514",
        )
        assert config.litellm_model == "openrouter/anthropic/claude-sonnet-4-20250514"

    def test_frozen_immutable(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("PROVIDER=openrouter\nAPI_KEY=sk-test\nMODEL=test/model\n")

        config = Config.from_env(env_file)
        with pytest.raises(AttributeError):
            config.model = "other"  # type: ignore[misc]


class TestGetConfig:
    def test_singleton(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PROVIDER", "openrouter")
        monkeypatch.setenv("API_KEY", "sk-test")
        monkeypatch.setenv("MODEL", "test/model")
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reload(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PROVIDER", "openrouter")
        monkeypatch.setenv("API_KEY", "sk-test")
        monkeypatch.setenv("MODEL", "model-a")
        c1 = get_config()
        monkeypatch.setenv("MODEL", "model-b")
        c2 = get_config(reload=True)
        assert c1.model == "model-a"
        assert c2.model == "model-b"
