"""Retry transient chat failures, including failures after streaming starts."""

from openai import OpenAIError

from surprisals_experiment.retry_policy import transient
from .stream_reply import IncompleteStreamError, stream_reply


async def reply(self, *, on_delta=None) -> str:
    history_length = len(self.messages)
    policy = self.retry_policy

    def before_sleep(state):
        # Keep failed partial output on disk, but retry the original conversation.
        del self.messages[history_length:]
        if on_delta is not None:
            on_delta("retry", f"{state.attempt_number}/{policy.retries} in {state.upcoming_sleep:g}s: "
                              f"{state.outcome.exception()}\n")

    try:
        async for attempt in policy.retrying(
            retryable=lambda error: transient(error) or isinstance(error, IncompleteStreamError),
            before_sleep=before_sleep,
        ):
            with attempt:
                return await stream_reply(self, on_delta=on_delta)
    except (OpenAIError, IncompleteStreamError) as error:
        raise RuntimeError(f"U chat request failed: {error}") from error
