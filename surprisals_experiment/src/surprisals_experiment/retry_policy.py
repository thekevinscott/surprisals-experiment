"""One retry budget and capped exponential schedule for chat and Pi."""

from dataclasses import dataclass

DEFAULT_LLM_RETRIES = 60


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = DEFAULT_LLM_RETRIES
    base_delay_ms: int = 5000
    max_delay_ms: int = 60000

    def pi_settings(self) -> dict:
        return {
            "enabled": self.retries > 0,
            "maxRetries": self.retries,
            "baseDelayMs": self.base_delay_ms,
            "maxAgentDelayMs": self.max_delay_ms,
        }
