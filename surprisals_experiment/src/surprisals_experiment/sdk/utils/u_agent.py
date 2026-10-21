"""Runtime arguments for U's image-defined Pi configuration."""

import shlex
from collections.abc import Callable

from botbox import PiAgent

from .u_retryable import u_retryable


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
        if event["type"] == "auto_retry_end":
            return not event["success"]
        if event["type"] == "agent_end":
            assistant = next((m for m in reversed(event.get("messages", []))
                              if m["role"] == "assistant"), None)
            if assistant is not None and u_retryable(assistant):
                return False
        return super().turn_ended(event)
