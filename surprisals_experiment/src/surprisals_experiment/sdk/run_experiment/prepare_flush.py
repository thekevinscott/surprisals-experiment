"""Seed a cleared chat U with the question and its shortest all-pass attempt."""

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


def prepare_flush(config: Config, history: list[Attempt]) -> str:
    question = config.question_file.read_text()
    best = min((attempt for attempt in history if attempt.passed),
               key=lambda attempt: (attempt.length, attempt.number), default=None)
    if best is None:
        return question
    return TURN(question=question.rstrip("\n"), attempt=best, unit=config.advice_measure.unit)
