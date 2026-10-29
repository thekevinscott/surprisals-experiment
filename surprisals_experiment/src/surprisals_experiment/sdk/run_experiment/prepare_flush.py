"""Seed a cleared chat U with its recent advice history."""

from importlib.resources import files

from surprisals_experiment.config import Config

TEMPLATE = files("surprisals_experiment").joinpath("prompts/u/flush/turn.txt").read_text().rstrip("\n")


def prepare_flush(config: Config, history: list[tuple[int, str, int | float, int]], *, feedback: str) -> str:
    return TEMPLATE.format(
        question=config.question_file.read_text(),
        history="\n".join(
            f'<advice attempt="{attempt}" length="{length}" '
            f'passed="{passed} of {config.t_samples}">\n{advice}\n</advice>'
            for attempt, advice, length, passed in history
        ),
        feedback=feedback,
    )
