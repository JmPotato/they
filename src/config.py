"""Minimal configuration — MODEL + generation parameters."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Immutable agent configuration."""

    provider: str
    api_key: str
    model: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 16384

    @property
    def litellm_model(self) -> str:
        """Return the LiteLLM model string: ``{provider}/{model}``."""
        return f"{self.provider}/{self.model}"

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Config":
        """Load configuration from environment / .env file.

        Raises:
            ValueError: If PROVIDER, API_KEY, or MODEL is not set.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        missing = [
            name for name in ("PROVIDER", "API_KEY", "MODEL") if not os.getenv(name)
        ]
        if missing:
            msg = f"{', '.join(missing)} required. Set in .env or as environment variables."
            raise ValueError(msg)

        return cls(
            provider=os.environ["PROVIDER"],
            api_key=os.environ["API_KEY"],
            model=os.environ["MODEL"],
            base_url=os.getenv("BASE_URL"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS", "16384")),
        )


# Global singleton
_config: Config | None = None


def get_config(reload: bool = False) -> Config:
    """Get the global Config instance (lazy-loaded singleton)."""
    global _config
    if _config is None or reload:
        _config = Config.from_env()
    return _config
