"""One advice's text and score artifacts on disk."""

import json
from hashlib import sha256

from surprisals_experiment.config import Config


class Advice:
    def __init__(self, config: Config, text: str):
        self.text = text
        self.directory = config.output / "advices" / sha256(text.encode("utf-8")).hexdigest()

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "advice.txt").write_bytes(self.text.encode("utf-8"))

    def write_score(self, score: int | float, tokens=None) -> None:
        (self.directory / "advice.json").write_text(json.dumps({
            "score": score, **({"tokens": tokens} if tokens is not None else {}),
        }, indent=2) + "\n")
