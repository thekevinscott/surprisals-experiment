"""One advice's text and cached score artifacts on disk."""

import json
from hashlib import sha256
from pathlib import Path

from .advice_measure import AdviceMeasure
from .utils.write import write


class Advice:
    def __init__(self, path: Path, measure: AdviceMeasure, root: Path):
        self.text = path.read_bytes().decode("utf-8")
        self.measure = measure
        self.directory = root / "advices" / sha256(self.text.encode("utf-8")).hexdigest()

    def save(self) -> None:
        write(self.directory / "advice.txt", self.text.encode("utf-8"))

    async def score(self, on_delta=None) -> int | float:
        path = self.directory / "advice.json"
        if path.exists():
            return json.loads(path.read_text())["score"]
        score, tokens = await self.measure.score(self.text, on_delta=on_delta)
        write(path, json.dumps({
            "score": score, **({"tokens": tokens} if tokens is not None else {}),
        }, indent=2) + "\n")
        return score
