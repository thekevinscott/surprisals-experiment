"""Serialize scorer lifecycle operations for one invocation directory."""

import fcntl
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def locked_state(directory: Path) -> Generator[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "runpod.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield directory / "runpod.json"
