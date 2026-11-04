"""One advice's text and score artifacts on disk."""

import json
from hashlib import sha256

from surprisals_experiment.config import Config
from .utils.write import write


class Advice:
    def __init__(self, config: Config, text: str):
        self.text = text
        self.directory = config.output / "advices" / sha256(text.encode("utf-8")).hexdigest()

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        write(self.directory / "advice.txt", self.text.encode("utf-8"))

    def write_score(self, score: int | float, tokens=None) -> None:
        write(self.directory / "advice.json", json.dumps({
            "score": score, **({"tokens": tokens} if tokens is not None else {}),
        }, indent=2) + "\n")
