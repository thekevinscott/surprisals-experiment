import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....utils.u_chat import ChatSession
from ....utils.write_text import write_text
from .save_advice import save_advice


async def write_advice(
    config: Config, u_session: ChatSession, messages: list[dict], *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> str:
    reply = await u_session.prompt(messages, on_delta=on_delta)
    advice = reply["content"]
    directory = config.advice_dir(attempt, 0)
    write_text(directory / "reply.json", json.dumps(reply, ensure_ascii=False) + "\n")
    save_advice(directory, advice)
    return advice
