"""Seed a cleared chat U with the experiment's best advice and recent history."""

from importlib.resources import files

from surprisals_experiment.config import Config

TEMPLATE = files("surprisals_experiment").joinpath("prompts/u/flush/turn.txt").read_text().rstrip("\n")


def prepare_flush(
    config: Config, history: list[tuple[int, str, int | float, int]], *,
    best_advice: str | None, best_length: int | float | None, feedback: str,
) -> str:
    none = "(none yet)"
    return TEMPLATE.format(
        question=config.question_file.read_text(),
        best_length=none if best_length is None else best_length,
        best_advice=none if best_advice is None else best_advice,
        history="\n".join(
            f'<advice attempt="{attempt}" measurement="{measurement}" '
            f'passed="{passed} of {config.t_samples}">\n{advice}\n</advice>'
            for attempt, advice, measurement, passed in history
        ),
        feedback=feedback,
    )
