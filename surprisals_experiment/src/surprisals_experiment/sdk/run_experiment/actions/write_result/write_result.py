import json
from pathlib import Path

from ....turn import Turn
from ....database import ExperimentDatabase
from ....utils.write import write

RESULT = Path(__file__).with_name("result.sql")


async def write_result(turn: Turn, database: ExperimentDatabase):
    config = turn.config
    result, = await database.query(RESULT, samples=config.t_samples)
    solution = config.output / result["turn_id"] / "ts/0/src" if result["turn_id"] else None
    write(config.result_file, json.dumps({
        **config.advice_measure.result_fields(result["score"]),
        "success": solution is not None,
        "attempts": result["attempts"],
        "solution": str(solution) if solution else None,
    }, indent=2) + "\n")
    return solution, result["stale"]
