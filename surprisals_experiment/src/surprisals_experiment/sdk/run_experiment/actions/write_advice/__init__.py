from collections.abc import Callable

from surprisals_experiment.config import Config
from ....utils.u_chat import ChatSession
from .save_advice import save_advice


async def write_advice(
    config: Config, u_session: ChatSession, prompt: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> str:
    advice = await u_session.prompt(prompt, on_delta=on_delta)
    directory = config.advice_dir(attempt, 0)
    save_advice(directory, advice)
    return advice
