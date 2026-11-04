from collections.abc import Callable

from ....turn import Turn
from ....utils.u_chat import ChatSession
from ....advice import Advice
from ....database import ExperimentDatabase, QuestionDatabase
from ...prepare_flush import prepare_flush


async def write_advice(
    turn: Turn, u_chat: ChatSession, database: ExperimentDatabase, problem: QuestionDatabase, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> Advice:
    config = turn.config
    prompt = await prepare_flush(config, problem, database)
    advice = Advice(await u_chat.prompt(prompt, on_delta=on_delta), config.advice_measure, config.output)
    turn.attempt_dir.mkdir(parents=True, exist_ok=True)
    advice.save()
    return advice
