"""Retry transient chat failures, including failures after streaming starts."""

from openai import OpenAIError

from surprisals_experiment.retry_policy import DELAYS, retried, transient
from .stream_reply import IncompleteStreamError, stream_reply


async def reply(self, *, on_delta=None) -> str:
    history_length = len(self.messages)

    def before_sleep(state):
        # Keep failed partial output on disk, but retry the original conversation.
        del self.messages[history_length:]
        if on_delta is not None:
            on_delta("retry", f"{state.attempt_number}/{len(DELAYS)} in {state.upcoming_sleep:g}s: "
                              f"{state.outcome.exception()}\n")

    @retried(lambda error: transient(error) or isinstance(error, IncompleteStreamError),
             operation="U chat request", before_sleep=before_sleep)
    async def request():
        return await stream_reply(self, on_delta=on_delta)

    try:
        return await request()
    except (OpenAIError, IncompleteStreamError) as error:
        raise RuntimeError(f"U chat request failed: {error}") from error
