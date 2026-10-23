"""Prompt U once and preserve its advice and measurement."""

from collections.abc import Callable

from surprisals_experiment.config import Config
from ..utils.u_session import USession
from ..utils.u_chat import ChatSession
from .save_advice import save_advice


async def prepare_advice(
    config: Config, u_session: USession | ChatSession, prompt: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> str:
    advice = await u_session.prompt(prompt, on_delta=on_delta)
    save_advice(config.advice_dir(attempt, 0), advice,
                rejected=False, measurement=len(advice))
    return advice
