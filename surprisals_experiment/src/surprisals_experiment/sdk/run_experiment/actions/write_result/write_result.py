import json

from ....run import Run
from ....utils.write import write
from .read_progress import read_progress


async def write_result(run: Run) -> None:
    config = run.config
    result, solution = await read_progress(run)
    write(config.result_file, json.dumps({
        **config.advice_measure.result_fields(result["score"]),
        "success": solution is not None,
        "attempts": result["attempts"],
        "solution": str(solution) if solution else None,
    }, indent=2) + "\n")
