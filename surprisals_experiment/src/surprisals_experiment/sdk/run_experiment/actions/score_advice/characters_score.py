import json
from collections.abc import Callable

from surprisals_experiment.config import Config


async def characters_score(
    config: Config, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    directory = config.attempt_dir(attempt)
    measurement = len(advice)
    (directory / "metadata.json").write_text(json.dumps({
        "measurement": measurement,
    }, indent=2) + "\n")
    return measurement
