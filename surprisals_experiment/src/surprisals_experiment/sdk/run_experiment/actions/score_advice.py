import json
from collections.abc import Callable

from dirsql import DirSQL

from surprisals_experiment.config import Config


async def scored_tokens(config: Config, advice: str) -> list[tuple[str, float]] | None:
    rows = await DirSQL(str(config.output), no_ignore=True).query(
        "SELECT m.path FROM './attempts/*/advices/*/advice.txt' AS a"
        " JOIN './attempts/*/advices/*/metadata.json' AS m ON m.dir = a.dir"
        f" WHERE a.content = '{advice.replace("'", "''")}' AND m.content ->> 'tokens' IS NOT NULL LIMIT 1"
    )
    return json.loads((config.output / rows[0]["path"]).read_text())["tokens"] if rows else None


async def score_advice(
    config: Config, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    directory = config.advice_dir(attempt, 0)
    measurement, tokens = await config.advice_measure.score(
        advice, tokens=await scored_tokens(config, advice), on_delta=on_delta)
    (directory / "metadata.json").write_text(json.dumps({
        "rejected": False,
        "measurement": measurement,
        **({"tokens": tokens} if tokens is not None else {}),
    }, indent=2) + "\n")
    return measurement
