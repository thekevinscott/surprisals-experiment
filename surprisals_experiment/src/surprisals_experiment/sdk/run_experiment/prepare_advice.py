"""Prompt U once and preserve its advice and measurement."""

import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ..utils.u_session import USession
from ..utils.u_chat import ChatSession
from .save_advice import save_advice


async def prepare_advice(
    config: Config, u_session: USession | ChatSession, prompt: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> tuple[str, int | float]:
    advice = await u_session.prompt(prompt, on_delta=on_delta)
    directory = config.advice_dir(attempt, 0)
    save_advice(directory, advice)
    measurement, tokens = await config.advice_measure.score(advice, on_delta=on_delta)
    (directory / "metadata.json").write_text(json.dumps({
        "rejected": False,
        "measurement": measurement,
        **({"tokens": tokens} if tokens is not None else {}),
    }, indent=2) + "\n")
    return advice, measurement
