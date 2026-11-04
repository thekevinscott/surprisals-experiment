import json
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ...database import ExperimentDatabase

SCORED_TOKENS = Path(__file__).parents[2] / "database" / "scored_tokens.sql"


async def scored_tokens(database: ExperimentDatabase, advice: str) -> list[tuple[str, float]] | None:
    rows = await database.query(SCORED_TOKENS, advice=advice)
    return json.loads(rows[0]["tokens"]) if rows else None


async def score_advice(
    config: Config, database: ExperimentDatabase, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    directory = config.attempt_dir(attempt)
    tokens = await scored_tokens(database, advice)
    if tokens is None:
        measurement, tokens = await config.advice_measure.score(advice, on_delta=on_delta)
    else:
        measurement = sum(bits for _, bits in tokens)
    (directory / "metadata.json").write_text(json.dumps({
        "rejected": False,
        "measurement": measurement,
        **({"tokens": tokens} if tokens is not None else {}),
    }, indent=2) + "\n")
    return measurement
