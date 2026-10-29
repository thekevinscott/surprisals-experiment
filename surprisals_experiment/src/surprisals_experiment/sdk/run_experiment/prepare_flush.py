"""Seed a cleared chat U with its previous attempts and their test results."""

from dataclasses import dataclass
from importlib.resources import files

from surprisals_experiment.config import Config

PROMPTS = files("surprisals_experiment").joinpath("prompts/u/flush")
TURN, ATTEMPT, CODE, CODE_T, CODE_FILE = (
    PROMPTS.joinpath(f"{name}.txt").read_text().rstrip("\n")
    for name in ("turn", "attempt", "code", "code_t", "code_file")
)


@dataclass
class Attempt:
    number: int
    advice: str
    length: int | float
    results: list[str]
    passed: bool
    sources: dict[str, dict[str, str]]


def render_code(attempt: Attempt) -> str:
    return CODE.format(implementations="\n".join(
        CODE_T.format(index=index, files="\n".join(
            CODE_FILE.format(path=path, source=source.rstrip("\n"))
            for path, source in attempt.sources.get(str(index), {}).items()
        ))
        for index in range(len(attempt.results))
    )) + "\n"


def render(config: Config, history: list[Attempt]) -> str:
    latest = history[-1:]
    latest_pass = next(([attempt] for attempt in reversed(history) if attempt.passed), [])
    shown = {attempt.number for attempt in latest + latest_pass}
    template = config.advice_measure.render(ATTEMPT)
    return TURN.format(
        question=config.question_file.read_text().rstrip("\n"),
        history="\n".join(
            template.format(
                number=attempt.number, length=attempt.length, advice=attempt.advice,
                results="\n".join(f"T-{index}: {result}" for index, result in enumerate(attempt.results)),
                code=render_code(attempt) if attempt.number in shown else "",
            )
            for attempt in history
        ),
    )


def prepare_flush(config: Config, history: list[Attempt]) -> str:
    kept = list(history)
    while kept and config.u_compact_chars and len(render(config, kept)) > config.u_compact_chars:
        failed = [attempt for attempt in kept if not attempt.passed]
        kept.remove(failed[0] if failed else kept[0])
    return render(config, kept)
