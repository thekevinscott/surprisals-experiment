"""A fresh Pi executor with live thinking and text callbacks."""

import shlex
from collections.abc import Callable

from .retrying_pi_agent import RetryingPiAgent

from .receive_event import receive_event


class TAgent(RetryingPiAgent):
    def __init__(self, provider: str, model: str, *, api_key: str,
                 instructions: str, on_delta: Callable[[str, str], None] | None):
        super().__init__(provider, model=model, api_key=api_key)
        self.instructions = instructions
        self.on_delta = on_delta

    def command(self, prompt: str) -> str:
        return super().command(prompt) + " --append-system-prompt " + shlex.quote(self.instructions)

    def receive(self, event: dict) -> None:
        receive_event(event, on_delta=self.on_delta)
