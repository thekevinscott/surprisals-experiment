"""Retry failed chat replies, including failures after streaming starts."""

from surprisals_experiment.retry_policy.constants import DELAYS
from surprisals_experiment.retry_policy.retried import retried
from tenacity import retry_if_exception_type, retry_if_not_exception_type

from .stream_reply.errors import OutputTokenLimitError
from .stream_reply.stream_reply import stream_reply


async def reply(self, *, on_delta=None) -> str:
    history_length = len(self.messages)

    def before_sleep(state):
        # Keep failed partial output on disk, but retry the original conversation.
        del self.messages[history_length:]
        if on_delta is not None:
            on_delta("retry", f"{state.attempt_number}/{len(DELAYS)} in {state.upcoming_sleep:g}s: "
                              f"{state.outcome.exception()}\n")

    @retried(operation="U chat request", before_sleep=before_sleep,
             retry=retry_if_exception_type() & retry_if_not_exception_type(OutputTokenLimitError))
    async def request():
        return await stream_reply(self, on_delta=on_delta)

    return await request()
