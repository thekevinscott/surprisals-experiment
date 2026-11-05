from tenacity import retry, stop_after_attempt, wait_chain, wait_fixed

from .constants import DELAYS


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
