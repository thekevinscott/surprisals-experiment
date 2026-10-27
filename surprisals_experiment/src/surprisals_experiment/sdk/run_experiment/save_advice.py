"""Save one advice candidate and its acceptance measurement."""

import json
from pathlib import Path


def save_advice(directory: Path, advice: str, *, rejected: bool, measurement: int | float) -> None:
    directory.mkdir(parents=True)
    (directory / "advice.txt").write_text(advice)
    (directory / "metadata.json").write_text(json.dumps({
        "rejected": rejected,
        "measurement": measurement,
    }, indent=2) + "\n")
