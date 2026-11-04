import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....advice import Advice


async def characters_score(
    config: Config, advice: Advice, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    measurement = len(advice.text)
    advice.write_score(measurement)
    (config.attempt_dir(attempt) / "metadata.json").write_text(
        json.dumps({"advice": advice.hash}, indent=2) + "\n"
    )
    return measurement
