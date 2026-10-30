"""Seed a cleared chat U with its previous attempts and their test results."""

from dataclasses import dataclass

from surprisals_experiment.config import Config
from surprisals_experiment.prompt import Prompt

TURN = Prompt("u/flush/turn.txt")


@dataclass
class Attempt:
    number: int
    advice: str
    length: int | float
    results: list[str]
    passed: bool
    sources: dict[str, dict[str, str]]
    tokens: list[tuple[str, float]] | None = None


def render(config: Config, history: list[Attempt]) -> str:
    latest = history[-1:]
    latest_pass = next(([attempt] for attempt in reversed(history) if attempt.passed), [])
    return TURN(
        question=config.question_file.read_text().rstrip("\n"),
        history=history,
        shown={attempt.number for attempt in latest + latest_pass},
        unit=config.advice_measure.unit,
    )


def prepare_flush(config: Config, history: list[Attempt]) -> str:
    kept = list(history)
    while kept and config.u_compact_chars and len(render(config, kept)) > config.u_compact_chars:
        failed = [attempt for attempt in kept if not attempt.passed]
        kept.remove(failed[0] if failed else kept[0])
    return render(config, kept)
