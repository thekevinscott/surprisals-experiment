import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....database import ExperimentDatabase


async def characters_score(
    config: Config, database: ExperimentDatabase, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int:
    measurement = len(advice)
    (config.attempt_dir(attempt) / "metadata.json").write_text(json.dumps({
        "rejected": False, "measurement": measurement,
    }, indent=2) + "\n")
    return measurement
