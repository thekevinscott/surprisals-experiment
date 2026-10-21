"""State and operations for one persistent U session."""

from dataclasses import dataclass
from pathlib import Path
from botbox import Session

from .prompt import prompt


@dataclass
class USession:
    pi_session: Session
    solutions: Path

    prompt = prompt
