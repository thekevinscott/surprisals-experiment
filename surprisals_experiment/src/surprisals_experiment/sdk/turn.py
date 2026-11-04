"""A turn's owning config and filesystem coordinates."""

import json
from dataclasses import dataclass
from pathlib import Path

from surprisals_experiment.config import Config
from .advice import Advice


@dataclass(frozen=True)
class Turn:
    config: Config
    position: int
    window: int = 0
    fork: int = 0

    @property
    def params(self) -> dict:
        return dict(window=self.window, fork=self.fork, turn=self.position)

    @property
    def attempt_dir(self) -> Path:
        return self.config.output / "windows" / str(self.window) / "forks" / str(self.fork) / "turns" / str(self.position)

    def t_dir(self, sample: int) -> Path:
        return self.attempt_dir / "ts" / str(sample)

    @property
    def u_dir(self) -> Path:
        return self.attempt_dir / "u"

    @property
    def u_transcripts(self) -> Path:
        return self.u_dir / "transcripts"

    @property
    def advice(self) -> Advice:
        metadata = json.loads((self.attempt_dir / "metadata.json").read_text())
        text = (self.config.output / metadata["advice"] / "advice.txt").read_bytes().decode("utf-8")
        return Advice(text, self.config.advice_measure, self.config.output)
