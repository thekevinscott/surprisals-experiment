from pathlib import Path

from surprisals_experiment.config import Config
from ...database import QuestionDatabase
from ...run_test_suite import TestSuiteResult
from ..prepare_feedback import describe_result
from ..prepare_flush import Attempt, prepare_flush
from ..read_implementations import read_sources


async def write_feedback(
    config: Config, attempt: int, advice: str,
    measurement: int | float, solutions: list[Path], results: list[TestSuiteResult],
    best_length: int | float | None, best_solution: Path | None,
    turns_without_improvement: int, history: list[Attempt], problem: QuestionDatabase,
) -> tuple[str, int | float | None, Path | None, int]:
    if (all(result.all_passed for result in results)
            and (best_length is None or measurement < best_length)):
        turns_without_improvement = 0
        best_solution = solutions[0]
        best_length = measurement
    else:
        turns_without_improvement += 1
    history.append(Attempt(
        attempt, advice, measurement,
        [describe_result(config, attempt, index, sample) for index, sample in enumerate(results)],
        all(result.all_passed for result in results), read_sources(solutions),
        config.advice_measure.scores.get(advice),
    ))
    prompt = await prepare_flush(config, problem, history)
    (config.attempt_dir(attempt) / "feedback.txt").write_text(prompt)
    return prompt, best_length, best_solution, turns_without_improvement
