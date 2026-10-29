"""Seed a cleared chat U with its previous advices and their test results."""

from importlib.resources import files

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult

TEMPLATE = files("surprisals_experiment").joinpath("prompts/u/flush/turn.txt").read_text().rstrip("\n")


def keep(history: list[tuple[int, str, int | float, list[TestSuiteResult]]], limit: int):
    kept = list(history)
    while len(kept) > limit:
        failed = [entry for entry in kept if not all(result.all_passed for result in entry[3])]
        kept.remove(failed[0] if failed else kept[0])
    return kept


def prepare_flush(
    config: Config, history: list[tuple[int, str, int | float, list[TestSuiteResult]]], *, feedback: str,
) -> str:
    return TEMPLATE.format(
        question=config.question_file.read_text(),
        history="\n".join(
            f'<attempt number="{attempt}" length="{length}" '
            f'passed="{sum(result.all_passed for result in results)} of {len(results)}">\n'
            f'<advice>\n{advice}\n</advice>\n'
            + "".join(f"T {index}: passed {result.passed} of {result.total} tests\n" for index, result in enumerate(results))
            + "</attempt>"
            for attempt, advice, length, results in keep(history, config.u_history)
        ),
        feedback=feedback,
    )
