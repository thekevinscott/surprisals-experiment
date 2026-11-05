"""A fork's owning config and filesystem coordinates."""

from dataclasses import dataclass
from pathlib import Path

from surprisals_experiment.config import Config


@dataclass(frozen=True)
class Fork:
    config: Config
    window: int = 0
    position: int = 0

    @property
    def params(self) -> dict:
        return dict(window=self.window, fork=self.position)

    @property
    def fork_dir(self) -> Path:
        return self.config.output / "windows" / str(self.window) / "forks" / str(self.position)
