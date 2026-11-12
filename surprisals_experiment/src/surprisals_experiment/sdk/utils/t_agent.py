"""A fresh Pi executor with live thinking and text callbacks."""

import json
import shlex
from collections.abc import Callable

from .receive_event import receive_event
from .retrying_pi_agent import RetryingPiAgent

MODELS = ".pi/agent/models.json"


class TAgent(RetryingPiAgent):
    def __init__(
        self,
        provider: str,
        model: str,
        *,
        route: str,
        api_key: str,
        instructions: str,
        on_delta: Callable[[str, str], None] | None,
    ):
        super().__init__(provider, model=model, api_key=api_key)
        self.route = route
        self.instructions = instructions
        self.on_delta = on_delta

    def command(self) -> str:
        return (
            super().command("@/advice/advice.md")
            + " --no-tools --system-prompt "
            + shlex.quote(self.instructions)
        )

    def stage_auth(self, home) -> None:
        super().stage_auth(home)
        content, _ = home.files[MODELS]
        models = json.loads(content)
        # One provider keeps T's behavior fixed.
        models["providers"][self.provider]["compat"] = {
            "openRouterRouting": {"only": [self.route], "allow_fallbacks": False}
        }
        home.write(MODELS, json.dumps(models))

    def receive(self, event: dict) -> None:
        receive_event(event, on_delta=self.on_delta)
