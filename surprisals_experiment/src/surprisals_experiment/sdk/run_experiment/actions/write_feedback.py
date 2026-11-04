from pathlib import Path

from surprisals_experiment.config import Config
from ...run_test_suite import read_summary
from ...utils.u_chat import ChatSession
from ..prepare_feedback import describe_result, prepare_feedback
from ..prepare_flush import Attempt, prepare_flush
from ..read_implementations import read_sources


def write_feedback(
    config: Config, u_session: ChatSession, attempt: int, advice: str,
    measurement: int | float, solutions: list[Path],
    best_length: int | float | None, best_solution: Path | None,
    turns_without_improvement: int, history: list[Attempt],
) -> tuple[str, int | float | None, Path | None, int]:
    all_passed = all(read_summary(solution.parent / "tests.json")["all_passed"] for solution in solutions)
    if (all_passed
            and (best_length is None or measurement < best_length)):
        turns_without_improvement = 0
        best_solution = solutions[0]
        best_length = measurement
        u_session.best_advice = advice
    else:
        turns_without_improvement += 1
    u_session.best_length = best_length
    u_session.turns_without_improvement = turns_without_improvement
    if config.u_flush:
        history.append(Attempt(
            attempt, advice, measurement,
            [describe_result(config, attempt, index) for index in range(len(solutions))],
            all_passed, read_sources(solutions),
            config.advice_measure.scores.get(advice),
        ))
        u_session.messages = u_session.messages[:1]
        prompt = prepare_flush(config, history)
        (config.attempt_dir(attempt) / "feedback.txt").write_text(prompt)
    else:
        prompt = prepare_feedback(
            config, attempt, solutions=solutions,
            advice_length=measurement,
            best_length=best_length, turns_without_improvement=turns_without_improvement,
        )
    return prompt, best_length, best_solution, turns_without_improvement
