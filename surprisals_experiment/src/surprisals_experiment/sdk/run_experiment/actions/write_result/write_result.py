import json
from pathlib import Path

from ....turn import Turn
from ....run import Run
from ....utils.write import write

RESULT = Path(__file__).with_name("result.sql")


async def read_progress(run: Run, turn: Turn):
    config = turn.config
    result, = await run.database.query(RESULT, **turn.params, samples=config.t_samples)
    solution = config.output / result["turn_id"] / "ts/0/src" if result["turn_id"] else None
    return result, solution


async def write_result(run: Run, turn: Turn) -> None:
    config = turn.config
    result, solution = await read_progress(run, turn)
    write(config.result_file, json.dumps({
        **config.advice_measure.result_fields(result["score"]),
        "success": solution is not None,
        "attempts": result["attempts"],
        "solution": str(solution) if solution else None,
    }, indent=2) + "\n")
