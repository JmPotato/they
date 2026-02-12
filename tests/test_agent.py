"""Tests for agent creation."""

import pytest

from src.agent import create_agent
from src.config import Config


@pytest.fixture
def agent():
    return create_agent(
        Config(provider="openrouter", api_key="test", model="test-model")
    )


class TestCreateAgent:
    def test_name_and_tools(self, agent):
        assert agent.name == "they"
        assert len(agent.tools) == 4

    def test_instructions_reference_all_tools(self, agent):
        for name in ("read_tool", "write_tool", "edit_tool", "bash_tool"):
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
