import json
from collections.abc import Callable
from pathlib import Path

from ....turn import Turn
from ....utils.u_chat import open_u_chat
from ....utils.write import write
from ....advice import Advice
from ....database import ExperimentDatabase, QuestionDatabase
from ...prepare_flush import prepare_flush

FORK_BEST = Path(__file__).parents[2] / "prepare_flush/fork_best.sql"


async def write_advice(
    turn: Turn, database: ExperimentDatabase, problem: QuestionDatabase, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> None:
    config = turn.config
    prompt = await prepare_flush(config, problem, database, query_file=FORK_BEST,
                                 window=turn.window, fork=turn.fork, cutoff=turn.position)
    async with open_u_chat(turn) as chat:
        chat.attempt = turn.position
        advice = Advice(await chat.prompt(prompt, on_delta=on_delta), config.advice_measure, config.output)
    advice.save()
    write(turn.attempt_dir / "metadata.json",
          json.dumps({"advice": str(advice.directory.relative_to(config.output))}, indent=2) + "\n")
