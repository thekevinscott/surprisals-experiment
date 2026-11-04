import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....utils.write import write


async def characters_score(
    config: Config, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    directory = config.attempt_dir(attempt)
    measurement = len(advice)
    write(directory / "metadata.json", json.dumps({
        "measurement": measurement,
    }, indent=2) + "\n")
    return measurement
