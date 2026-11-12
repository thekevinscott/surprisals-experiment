"""Render the cached advice measurement shared by flush and in-window feedback."""

from surprisals_experiment.prompt import Prompt

MEASUREMENT = Prompt("u/measurement.txt")


def measurement(unit: str, attempt: dict) -> str:
    return MEASUREMENT(unit=unit, attempt=attempt).rstrip("\n")
