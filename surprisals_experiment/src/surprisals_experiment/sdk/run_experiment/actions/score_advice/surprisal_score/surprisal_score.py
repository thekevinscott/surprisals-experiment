import json
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .....database import ExperimentDatabase

MATCHING_ADVICE = Path(__file__).parent / "matching_advice.sql"


async def surprisal_score(
    config: Config, database: ExperimentDatabase, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    matching_advice = await database.query(MATCHING_ADVICE, advice=advice)
    if matching_advice:
        measurement = matching_advice[0]["score"]
        metadata = config.output / matching_advice[0]["turn_id"] / "metadata.json"
        tokens = json.loads(metadata.read_text())["tokens"]
    else:
        measurement, tokens = await config.advice_measure.score(advice, on_delta=on_delta)
    (config.attempt_dir(attempt) / "metadata.json").write_text(json.dumps({
        "rejected": False,
        "measurement": measurement,
        "tokens": tokens,
    }, indent=2) + "\n")
    return measurement
