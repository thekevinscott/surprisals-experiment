import json
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ....database import ExperimentDatabase

SCORED_TOKENS = Path(__file__).parent / "scored_tokens.sql"


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


async def surprisal_score(
    config: Config, database: ExperimentDatabase, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    matching_advice = await database.query(SCORED_TOKENS, advice=advice)
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
