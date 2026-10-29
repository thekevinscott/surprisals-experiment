"""Seed a cleared chat U with its previous advices and their test results."""

from importlib.resources import files

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult

PROMPTS = files("surprisals_experiment").joinpath("prompts/u/flush")
TEMPLATE = PROMPTS.joinpath("turn.txt").read_text().rstrip("\n")
ATTEMPT = PROMPTS.joinpath("attempt.txt").read_text().rstrip("\n")


def render(config: Config, history: list[tuple[int, str, int | float, list[TestSuiteResult]]], feedback: str) -> str:
    return TEMPLATE.format(
        question=config.question_file.read_text(),
        history="\n".join(
            ATTEMPT.format(
                number=attempt, length=length, advice=advice,
                passed=sum(result.all_passed for result in results), total=len(results),
                results="".join(f"T {index}: passed {result.passed} of {result.total} tests\n" for index, result in enumerate(results)),
            )
            for attempt, advice, length, results in history
        ),
        feedback=feedback,
    )


def prepare_flush(
    config: Config, history: list[tuple[int, str, int | float, list[TestSuiteResult]]], *, feedback: str,
) -> str:
    kept = list(history)
    while kept and config.u_compact_chars and len(render(config, kept, feedback)) > config.u_compact_chars:
        failed = [entry for entry in kept if not all(result.all_passed for result in entry[3])]
        kept.remove(failed[0] if failed else kept[0])
    return render(config, kept, feedback)
