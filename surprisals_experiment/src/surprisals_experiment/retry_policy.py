"""Fixed retry schedules for transient failures; Pi owns its internal retries."""

from openai import APIConnectionError, APIError, APIStatusError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_chain, wait_fixed

DELAYS = (10, 30, 60, 120, 300, 600, 1800, 3600)
PI_RETRIES = 60
PI_BASE_DELAY_MS = 5000
PI_MAX_DELAY_MS = 60000


def transient(error: BaseException) -> bool:
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or error.status_code >= 500
    if type(error) is APIError:
        # OpenRouter can report upstream failures in an in-stream error chunk.
        code = error.body.get("code") if isinstance(error.body, dict) else None
        return isinstance(code, int) and (code == 429 or code >= 500)
    return isinstance(error, APIConnectionError)


def retried(retryable, *, operation: str, before_sleep=None):
    def exhausted(state):
        error = state.outcome.exception()
        detail = " ".join(str(error).splitlines())
        raise RuntimeError(
            f"{operation} failed: {detail}; {state.attempt_number - 1} retries exhausted"
        ) from error

    return retry(
        retry=retry_if_exception(retryable),
        stop=stop_after_attempt(len(DELAYS) + 1),
        wait=wait_chain(*(wait_fixed(delay) for delay in DELAYS)),
        before_sleep=before_sleep,
        retry_error_callback=exhausted,
        reraise=True,
    )


def pi_settings() -> dict:
    return {
        "enabled": True,
        "maxRetries": PI_RETRIES,
        "baseDelayMs": PI_BASE_DELAY_MS,
        "maxAgentDelayMs": PI_MAX_DELAY_MS,
    }
