"""Stage the shared retry policy in both Pi agents' fresh homes."""

import json

from botbox import PiAgent

from surprisals_experiment.retry_policy import DEFAULT_LLM_RETRIES, RetryPolicy


class RetryingPiAgent(PiAgent):
    def __init__(self, *args, llm_retries=DEFAULT_LLM_RETRIES, compaction=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_policy = RetryPolicy(llm_retries)
        self.compaction = compaction

    def stage_auth(self, home) -> None:
        super().stage_auth(home)
        home.write(".pi/agent/settings.json", json.dumps({
            "retry": self.retry_policy.pi_settings(),
            "compaction": {"enabled": self.compaction},
        }))
