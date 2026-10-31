"""Stage the Pi retry settings in T's fresh home."""

import json

from botbox import PiAgent

from surprisals_experiment.retry_policy import pi_settings


class RetryingPiAgent(PiAgent):
    def stage_auth(self, home) -> None:
        super().stage_auth(home)
        home.write(".pi/agent/settings.json", json.dumps({
            "retry": pi_settings(),
            "compaction": {"enabled": True},
        }))
