import traceback
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ....advice import Advice
from ....database import ExperimentDatabase
from ....utils.write import write
from ...queries import query
from .prompt_t_to_produce_code import prompt_t_to_produce_code

SAMPLES = Path(__file__).parents[2] / "queries/samples.sql"


async def write_solutions(
    config: Config, database: ExperimentDatabase, advice: Advice, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> list[Path]:
    samples = await query(database, config, SAMPLES)
    try:
        return await prompt_t_to_produce_code(
            config, advice=advice, on_delta=on_delta,
            folders=[config.t_dir(config.position["turn"], sample["position"]) for sample in samples
                     if sample["state"] == "solutions_missing"],
        )
    except Exception:
        write(config.attempt_dir(config.position["turn"]) / "error.txt", traceback.format_exc())
        raise
