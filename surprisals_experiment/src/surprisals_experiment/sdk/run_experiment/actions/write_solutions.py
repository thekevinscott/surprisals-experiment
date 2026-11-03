import traceback
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ..prompt_t_to_produce_code import prompt_t_to_produce_code


async def write_solutions(
    config: Config, *, attempt: int, advice: str, snapshot: Path,
    on_delta: Callable[[str, str], None] | None = None,
    samples: list[int] | None = None,
    retry_budgets: dict[int, int] | None = None,
) -> list[Path]:
    try:
        return await prompt_t_to_produce_code(
            config, attempt=attempt, advice=advice,
            snapshot=snapshot, on_delta=on_delta,
            samples=samples, retry_budgets=retry_budgets,
        )
    except Exception:
        (config.attempt_dir(attempt) / "error.txt").write_text(traceback.format_exc())
        raise
