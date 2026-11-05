from tenacity import retry as tenacity_retry
from tenacity import retry_if_exception_type, stop_after_attempt, wait_chain, wait_fixed

from .constants import DELAYS


def retried(*, operation: str, before_sleep=None, retry=None):
    def exhausted(state):
        error = state.outcome.exception()
        detail = " ".join(str(error).splitlines())
        raise RuntimeError(
            f"{operation} failed: {detail}; {state.attempt_number - 1} retries exhausted"
        ) from error

    return tenacity_retry(
        retry=retry if retry is not None else retry_if_exception_type(),
        stop=stop_after_attempt(len(DELAYS) + 1),
        wait=wait_chain(*(wait_fixed(delay) for delay in DELAYS)),
        before_sleep=before_sleep,
        retry_error_callback=exhausted,
        reraise=True,
    )
