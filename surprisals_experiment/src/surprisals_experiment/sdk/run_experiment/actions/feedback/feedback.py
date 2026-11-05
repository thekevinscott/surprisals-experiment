from ....run import Run
from ....turn import Turn
from ..write_feedback import write_feedback
from ..write_result import write_result


async def feedback(run: Run, turn: Turn):
    await write_feedback(turn, run.database, run.problem)
    await write_result(run, turn)
