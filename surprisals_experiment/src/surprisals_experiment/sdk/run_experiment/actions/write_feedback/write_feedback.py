from pathlib import Path

from surprisals_experiment.config import Config
from ....database import ExperimentDatabase, QuestionDatabase
from ....utils.u_chat import ChatSession
from ...prepare_feedback import describe_result, prepare_feedback
from ...prepare_flush import Attempt, prepare_flush
from ...read_implementations import read_sources

TURN_TESTS = Path(__file__).parent / "turn_tests.sql"


async def write_feedback(
    config: Config, u_chat: ChatSession, database: ExperimentDatabase, attempt: int, advice: str,
    measurement: int | float, solutions: list[Path],
    best_length: int | float | None, best_solution: Path | None,
    turns_without_improvement: int, history: list[Attempt], problem: QuestionDatabase,
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
        u_chat.best_advice = advice
    else:
        turns_without_improvement += 1
    u_chat.best_length = best_length
    u_chat.turns_without_improvement = turns_without_improvement
    if config.u_flush:
        history.append(Attempt(
            attempt, advice, measurement,
            [describe_result(config, attempt, index, sample) for index, sample in enumerate(results)],
            all_passed, read_sources(solutions),
            config.advice_measure.scores.get(advice),
        ))
        u_chat.messages = u_chat.messages[:1]
        prompt = await prepare_flush(config, problem, history)
        (config.attempt_dir(attempt) / "feedback.txt").write_text(prompt)
    else:
        prompt = prepare_feedback(
            config, attempt, results, solutions=solutions,
            advice_length=measurement,
            best_length=best_length, turns_without_improvement=turns_without_improvement,
        )
    return prompt, best_length, best_solution, turns_without_improvement
