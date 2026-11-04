from ....turn import Turn
from ....utils.write import write
from ....database import ExperimentDatabase, QuestionDatabase
from ...prepare_flush import prepare_flush


async def write_feedback(turn: Turn, database: ExperimentDatabase, problem: QuestionDatabase):
    prompt = await prepare_flush(turn.config, problem, database)
    write(turn.attempt_dir / "feedback.txt", prompt)
