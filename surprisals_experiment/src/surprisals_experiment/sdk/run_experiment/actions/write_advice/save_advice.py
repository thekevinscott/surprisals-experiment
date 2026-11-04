"""Preserve advice before calling the scorer."""

from pathlib import Path
from ....utils.write import write


def save_advice(directory: Path, advice: str) -> None:
    write(directory / "advice.txt", advice)
