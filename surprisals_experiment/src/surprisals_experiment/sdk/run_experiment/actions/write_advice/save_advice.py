"""Preserve exact advice bytes in their content-addressed folder."""

from hashlib import sha256
from pathlib import Path

from surprisals_experiment.config import Config


def save_advice(config: Config, advice: str) -> Path:
    content = advice.encode("utf-8")
    directory = config.output / "advices" / sha256(content).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "advice.txt").write_bytes(content)
    return directory
