import json
from pathlib import Path

from surprisals_experiment.config import Config


def write_result(config: Config, *, attempt: int, best_length: int | float | None, best_solution: Path | None):
    config.result_file.write_text(json.dumps({
        **config.advice_measure.result_fields(best_length),
        "success": best_solution is not None,
        "attempts": attempt + 1,
        "solution": str(best_solution) if best_solution is not None else None,
    }, indent=2) + "\n")
