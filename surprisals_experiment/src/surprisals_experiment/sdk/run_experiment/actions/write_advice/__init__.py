from collections.abc import Callable

from surprisals_experiment.config import Config
from ....utils.u_chat import ChatSession
from .save_advice import save_advice


async def write_advice(
    config: Config, u_chat: ChatSession, prompt: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> str:
    advice = await u_chat.prompt(prompt, on_delta=on_delta)
    directory = config.attempt_dir(attempt)
    directory.mkdir(parents=True, exist_ok=True)
    save_advice(config, advice)
    return advice
