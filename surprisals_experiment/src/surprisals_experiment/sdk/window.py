"""A window's owning config and filesystem coordinates."""

from dataclasses import dataclass
from pathlib import Path

from surprisals_experiment.config import Config


@dataclass(frozen=True)
class Window:
    config: Config
    position: int = 0

    @property
    def params(self) -> dict:
        return dict(window=self.position)

    @property
    def window_dir(self) -> Path:
        return self.config.output / "windows" / str(self.position)
