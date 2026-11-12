"""One advice's text and cached score artifacts on disk."""

import json
from hashlib import sha256
from pathlib import Path

from .advice_measure import AdviceMeasure
from .utils.write import write


class Advice:
    def __init__(self, root: Path, id: str, measure: AdviceMeasure):
        self.id = id
        self.directory = root / id
        self.measure = measure

    @classmethod
    def save(cls, text: str, measure: AdviceMeasure, root: Path) -> "Advice":
        advice = cls(root, f"advices/{sha256(text.encode('utf-8')).hexdigest()}", measure)
        write(advice.directory / "advice.txt", text.encode("utf-8"))
        if not (advice.directory / "advice.json").exists():
            write(advice.directory / "advice.json", "{}\n")
        return advice

    @property
    def text(self) -> str:
        return (self.directory / "advice.txt").read_bytes().decode("utf-8")

    async def score(self, on_delta=None) -> int | float:
        path = self.directory / "advice.json"
        if path.exists():
            metadata = json.loads(path.read_text())
            if "score" in metadata:
                return metadata["score"]
        score, tokens = await self.measure.score(self.text, on_delta=on_delta)
        write(path, json.dumps({
            "score": score, **({"tokens": tokens} if tokens is not None else {}),
        }, indent=2) + "\n")
        return score
