"""One T sample's coordinates within a turn."""

from dataclasses import dataclass
from pathlib import Path

from .turn import Turn


@dataclass(frozen=True)
class Sample:
    turn: Turn
    position: int

    @property
    def params(self) -> dict:
        return dict(**self.turn.params, sample=self.position)

    @property
    def t_dir(self) -> Path:
        return self.turn.t_dir(self.position)
