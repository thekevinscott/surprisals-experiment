"""One advice's text and cached score artifacts on disk."""

import json
from hashlib import sha256
from pathlib import Path

from surprisals_experiment.prompt import Prompt

from .advice_measure import AdviceMeasure
from .utils.write import write


MEASUREMENT = Prompt("u/measurement.txt")


class Advice:
    def __init__(self, root: Path, text: str, measure: AdviceMeasure):
        self.text = text
        self.measure = measure
        self.id = f"advices/{sha256(text.encode('utf-8')).hexdigest()}"
        self.directory = root / self.id
        path = self.directory / "advice.json"
        self.metadata = json.loads(path.read_text()) if path.exists() else {}
        self.save()

    @classmethod
    def load(cls, root: Path, id: str, measure: AdviceMeasure) -> "Advice":
        return cls(root, (root / id / "advice.txt").read_bytes().decode("utf-8"), measure)

    def save(self) -> None:
        write(self.directory / "advice.txt", self.text.encode("utf-8"))
        write(self.directory / "advice.json", json.dumps(self.metadata, indent=2) + "\n")

    async def score(self, on_delta=None) -> int | float:
        if "score" in self.metadata:
            return self.metadata["score"]
        score, tokens = await self.measure.score(self.text, on_delta=on_delta)
        self.metadata = {"score": score, **({"tokens": tokens} if tokens is not None else {})}
        self.save()
        return score

    @property
    def measurement(self) -> str:
        tokens = self.metadata.get("tokens")
        return MEASUREMENT(
            unit=self.measure.unit, score=self.metadata["score"],
            score_text="".join(f"{token}<{bits:.1f}>" for token, bits in tokens) if tokens is not None else None,
        ).rstrip("\n")
