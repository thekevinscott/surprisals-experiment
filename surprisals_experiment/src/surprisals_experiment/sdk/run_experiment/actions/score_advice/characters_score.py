import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....advice import Advice
from ....utils.write import write


async def characters_score(
    config: Config, advice: Advice, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    measurement = len(advice.text)
    advice.write_score(measurement)
    write(config.attempt_dir(attempt) / "metadata.json",
        json.dumps({"advice": str(advice.directory.relative_to(config.output))}, indent=2) + "\n"
    )
    return measurement
