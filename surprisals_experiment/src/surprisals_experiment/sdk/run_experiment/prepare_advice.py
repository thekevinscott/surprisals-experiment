"""Prompt U until its advice fits the cap, preserving every candidate."""

from collections.abc import Callable

from surprisals_experiment.config import Config
from ..utils.u_session import USession
from .save_advice import save_advice


async def prepare_advice(
    config: Config, u_session: USession, prompt: str, *, attempt: int, max_chars: int | None,
    on_delta: Callable[[str, str], None] | None = None,
) -> str:
    tries = 0
    while True:
        if tries > config.u_advice_retries:
            raise RuntimeError(
                f"U advice exceeded the character limit after {config.u_advice_retries} retries"
            )
        advice = await u_session.prompt(prompt, on_delta=on_delta)
        measurement = len(advice)
        rejected = max_chars is not None and measurement >= max_chars
        save_advice(config.advice_dir(attempt, tries), advice,
                    rejected=rejected, measurement=measurement)
        if not rejected:
            return advice
        tries += 1
        prompt = (f"Your advice was {measurement} characters. It must be fewer than "
                  f"{max_chars} characters, including spaces and newlines. "
                  "Rewrite it to meet that limit. Return only the instructions to T.")
