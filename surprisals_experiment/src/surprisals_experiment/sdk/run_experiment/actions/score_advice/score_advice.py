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
    directory = config.attempt_dir(attempt)
    rows = await database.query(SCORED_TOKENS, advice=advice) if config.cap_strategy == "surprisal" else []
    if rows:
        measurement = rows[0]["score"]
        metadata = config.output / rows[0]["turn_id"] / "metadata.json"
        tokens = json.loads(metadata.read_text())["tokens"]
    else:
        measurement, tokens = await config.advice_measure.score(advice, on_delta=on_delta)
    (directory / "metadata.json").write_text(json.dumps({
        "rejected": False,
        "measurement": measurement,
        **({"tokens": tokens} if tokens is not None else {}),
    }, indent=2) + "\n")
    return measurement
