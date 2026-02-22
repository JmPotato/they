"""they — AI Native Agent entry point."""

import asyncio
import os


def _configure() -> None:
    """Set up LiteLLM and agents SDK before anything else imports them."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    os.environ.setdefault("LITELLM_LOG", "ERROR")

    import litellm

    litellm.suppress_debug_info = True

    from agents import set_tracing_disabled

    set_tracing_disabled(True)


async def main() -> None:
    _configure()

    from src.agent import create_agent
    from src.tui import run_loop

    agent = create_agent()
    await run_loop(agent)


def main_sync() -> None:
    """Synchronous CLI entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt, EOFError:
        pass


if __name__ == "__main__":
    main_sync()
