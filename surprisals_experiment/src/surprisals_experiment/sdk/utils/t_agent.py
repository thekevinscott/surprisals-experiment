"""A fresh Pi executor with live thinking and text callbacks."""

import json
import shlex
from collections.abc import Callable

from botbox import PiAgent

from .receive_event import receive_event


class TAgent(PiAgent):
    def __init__(self, provider: str, model: str, *, api_key: str,
                 instructions: str, on_delta: Callable[[str, str], None] | None):
        super().__init__(provider, model=model, api_key=api_key)
        self.instructions = instructions
        self.on_delta = on_delta

    def stage_auth(self, home) -> None:
        super().stage_auth(home)
        home.write(".pi/agent/settings.json", json.dumps({
            "retry": {"enabled": False},
            "compaction": {"enabled": True},
        }))

    def command(self, prompt: str) -> str:
        return super().command(prompt) + " --append-system-prompt " + shlex.quote(self.instructions)

    def receive(self, event: dict) -> None:
        receive_event(event, on_delta=self.on_delta)
