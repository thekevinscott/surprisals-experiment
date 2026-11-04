import json
from pathlib import Path

from surprisals_experiment.config import Config
from ....utils.write import write


def write_result(config: Config, *, attempt: int, best_length: int | float | None, best_solution: Path | None):
    write(config.result_file, json.dumps({
        **config.advice_measure.result_fields(best_length),
        "success": best_solution is not None,
        "attempts": attempt + 1,
        "solution": str(best_solution) if best_solution is not None else None,
    }, indent=2) + "\n")
