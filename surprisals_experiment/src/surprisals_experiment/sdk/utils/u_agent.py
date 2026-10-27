"""Runtime arguments for U's image-defined Pi configuration."""

import shlex
from collections.abc import Callable

from botbox import PiAgent


class UAgent(PiAgent):
    def __init__(self, provider: str, model: str, *, api_key: str, thinking: str):
        super().__init__(provider, model=model, api_key=api_key)
        self.thinking = thinking
        self.on_event: Callable[[dict], None] | None = None

    def session_command(self) -> str:
        return shlex.join([
            "u-pi", "--provider", self.provider, "--model", self.model,
            "--thinking", self.thinking,
            "--system-prompt", "/u-config/u.txt",
        ])

    def turn_ended(self, event: dict) -> bool:
        # Botbox calls this for every parsed event, before buffering the next one.
        if self.on_event is not None:
            self.on_event(event)
        return super().turn_ended(event)
