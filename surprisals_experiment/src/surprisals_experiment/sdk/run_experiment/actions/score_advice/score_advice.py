import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....database import ExperimentDatabase
from .surprisal_score import surprisal_score


async def score_advice(
    config: Config, database: ExperimentDatabase, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    if config.cap_strategy == "characters":
        measurement = len(advice)
        (config.attempt_dir(attempt) / "metadata.json").write_text(json.dumps({
            "rejected": False, "measurement": measurement,
        }, indent=2) + "\n")
        return measurement
    return await surprisal_score(config, database, advice, attempt=attempt, on_delta=on_delta)
