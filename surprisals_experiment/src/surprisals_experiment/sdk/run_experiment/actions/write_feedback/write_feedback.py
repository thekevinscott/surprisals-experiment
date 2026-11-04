from pathlib import Path

from surprisals_experiment.config import Config
from ....utils.write import write
from ....database import ExperimentDatabase, QuestionDatabase
from ...prepare_flush import prepare_flush

TURN_TESTS = Path(__file__).parent / "turn_tests.sql"


async def write_feedback(
    config: Config, database: ExperimentDatabase, attempt: int, advice: str,
    measurement: int | float, solutions: list[Path],
    best_length: int | float | None, best_solution: Path | None,
    turns_without_improvement: int, problem: QuestionDatabase,
) -> tuple[str, int | float | None, Path | None, int]:
    results = await database.query(
        TURN_TESTS, window=int(config.window_dir.name), fork=int(config.fork_dir.name), turn=attempt,
    )
    all_passed = len(results) == config.t_samples and all(result["all_passed"] for result in results)
    if (all_passed
            and (best_length is None or measurement < best_length)):
        turns_without_improvement = 0
        best_solution = solutions[0]
        best_length = measurement
    else:
        turns_without_improvement += 1
    prompt = await prepare_flush(config, problem, database)
    write(config.attempt_dir(attempt) / "feedback.txt", prompt)
    return prompt, best_length, best_solution, turns_without_improvement
