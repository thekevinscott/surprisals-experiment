"""One retry budget and capped exponential schedule for chat, scoring, and Pi."""

from dataclasses import dataclass

from openai import APIConnectionError, APIError, APIStatusError
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

DEFAULT_LLM_RETRIES = 60


def transient(error: BaseException) -> bool:
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or error.status_code >= 500
    if type(error) is APIError:
        # OpenRouter can report upstream failures in an in-stream error chunk.
        code = error.body.get("code") if isinstance(error.body, dict) else None
        return isinstance(code, int) and (code == 429 or code >= 500)
    return isinstance(error, APIConnectionError)


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = DEFAULT_LLM_RETRIES
    base_delay_ms: int = 5000
    max_delay_ms: int = 60000

    def retrying(self, *, before_sleep=None, retryable=transient) -> AsyncRetrying:
        return AsyncRetrying(
            retry=retry_if_exception(retryable),
            stop=stop_after_attempt(self.retries + 1),
            wait=wait_exponential(multiplier=self.base_delay_ms / 1000, max=self.max_delay_ms / 1000),
            before_sleep=before_sleep,
            reraise=True,
        )

    def pi_settings(self) -> dict:
        return {
            "enabled": self.retries > 0,
            "maxRetries": self.retries,
            "baseDelayMs": self.base_delay_ms,
            "maxAgentDelayMs": self.max_delay_ms,
        }
