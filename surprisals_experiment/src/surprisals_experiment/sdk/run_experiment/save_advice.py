"""Preserve advice before calling the scorer."""

from pathlib import Path


def save_advice(directory: Path, advice: str) -> None:
    directory.mkdir(parents=True)
    (directory / "advice.txt").write_text(advice)
