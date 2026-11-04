"""Preserve advice before calling the scorer."""

from pathlib import Path
from ....utils.write_text import write_text


def save_advice(directory: Path, advice: str) -> None:
    write_text(directory / "advice.txt", advice)
