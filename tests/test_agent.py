"""Tests for agent creation."""

import pytest

from src.agent import SYSTEM_PROMPT, create_agent
from src.config import Config


@pytest.fixture
def agent():
    return create_agent(
        Config(provider="openrouter", api_key="test", model="test-model")
    )


class TestCreateAgent:
    def test_name_and_tools(self, agent):
        assert agent.name == "they"
        assert len(agent.tools) == 6
        assert agent.model_settings.include_usage is True

    def test_instructions_reference_all_tools(self, agent):
        for name in (
            "read_tool",
            "write_tool",
            "edit_tool",
            "bash_tool",
            "mark_tool",
            "recall_tool",
        ):
            assert name in agent.instructions

    def test_model_settings(self):
        agent = create_agent(
            Config(
                provider="openrouter",
                api_key="test",
                model="test-model",
                temperature=0.3,
                max_tokens=1024,
            )
        )
        assert agent.model_settings.temperature == 0.3
        assert agent.model_settings.max_tokens == 1024

    def test_default_model_settings(self, agent):
        assert agent.model_settings.temperature is None
        assert agent.model_settings.max_tokens is None

    def test_system_prompt_exported(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert "they" in SYSTEM_PROMPT
