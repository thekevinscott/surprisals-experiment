"""Stage the Pi retry settings in both Pi agents' fresh homes."""

import json

from botbox import PiAgent

from surprisals_experiment.retry_policy import pi_settings


class RetryingPiAgent(PiAgent):
    def __init__(self, *args, compaction=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.compaction = compaction if compaction is not None else {"enabled": True}

    def stage_auth(self, home) -> None:
        super().stage_auth(home)
        home.write(".pi/agent/settings.json", json.dumps({
            "retry": pi_settings(),
            "compaction": self.compaction,
        }))
