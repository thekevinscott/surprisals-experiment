"""Fixed retry schedule for any failure; Pi owns its internal retries."""

from itertools import pairwise

from tenacity import retry, stop_after_attempt, wait_chain, wait_fixed

RETRY_AT_SECONDS = (10, 30, 60, 120, 300, 600, 1800, 3600)
DELAYS = tuple(end - start for start, end in pairwise((0, *RETRY_AT_SECONDS)))
PI_RETRIES = 60
PI_BASE_DELAY_MS = 5000
PI_MAX_DELAY_MS = 60000


def retried(*, operation: str, before_sleep=None):
    def exhausted(state):
        error = state.outcome.exception()
        detail = " ".join(str(error).splitlines())
        raise RuntimeError(
            f"{operation} failed: {detail}; {state.attempt_number - 1} retries exhausted"
        ) from error

    return retry(
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
