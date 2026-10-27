"""A fresh Pi executor with live thinking and text callbacks."""

import shlex
from collections.abc import Callable

from botbox import PiAgent

from .receive_event import receive_event


class TAgent(PiAgent):
    def __init__(self, provider: str, model: str, *, api_key: str,
                 instructions: str, on_delta: Callable[[str, str], None] | None):
        super().__init__(provider, model=shlex.quote(model), api_key=api_key)
        self.instructions = instructions
        self.on_delta = on_delta

    def session_command(self) -> str:
        # Unlike PiAgent's, keeps message_update events: they carry the live deltas.
        return self._pi("--mode rpc --append-system-prompt " + shlex.quote(self.instructions))

    def turn_ended(self, event: dict) -> bool:
        receive_event(event, on_delta=self.on_delta)
        return super().turn_ended(event)
