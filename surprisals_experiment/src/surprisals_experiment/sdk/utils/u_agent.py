"""Runtime arguments for U's image-defined Pi configuration."""

import shlex
from collections.abc import Callable

from .retrying_pi_agent import RetryingPiAgent


class UAgent(RetryingPiAgent):
    def __init__(self, provider: str, model: str, *, api_key: str, thinking: str):
        super().__init__(provider, model=model, api_key=api_key,
                         # Pi compacts above contextWindow - reserveTokens:
                         # 1,048,576 - 917,504 = 131,072 tokens for the configured MiMo model.
                         compaction={"enabled": True, "reserveTokens": 917504})
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
