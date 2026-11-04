import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....utils.u_chat import open_u_chat
from ....utils.write import write
from ....database import ExperimentDatabase, QuestionDatabase
from ....advice import Advice
from ...prepare_flush import prepare_flush


async def write_advice(
    config: Config, database: ExperimentDatabase, problem: QuestionDatabase, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> None:
    prompt = await prepare_flush(config, problem, database)
    async with open_u_chat(config) as chat:
        chat.attempt = config.position["turn"]
        advice = Advice(await chat.prompt(prompt, on_delta=on_delta), config.advice_measure, config.output)
    advice.save()
    write(config.attempt_dir(config.position["turn"]) / "metadata.json",
          json.dumps({"advice": str(advice.directory.relative_to(config.output))}, indent=2) + "\n")
