"""Retry failed chat replies, including failures after streaming starts."""

from surprisals_experiment.retry_policy import DELAYS, retried
from .stream_reply import stream_reply


async def reply(self, messages: list[dict], *, on_delta=None) -> dict:
    def before_sleep(state):
        if on_delta is not None:
            on_delta("retry", f"{state.attempt_number}/{len(DELAYS)} in {state.upcoming_sleep:g}s: "
                              f"{state.outcome.exception()}\n")

    @retried(operation="U chat request", before_sleep=before_sleep)
    async def request():
        return await stream_reply(self, messages, on_delta=on_delta)

    return await request()
