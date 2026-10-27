"""Retry transient chat failures, including failures after streaming starts."""

from openai import APIConnectionError, APIError, APIStatusError, OpenAIError
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from .stream_reply import IncompleteStreamError, stream_reply


def transient(error: BaseException) -> bool:
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or error.status_code >= 500
    if type(error) is APIError:
        # OpenRouter reports upstream failures after the 200 as an in-stream error chunk.
        code = error.body.get("code") if isinstance(error.body, dict) else None
        return isinstance(code, int) and (code == 429 or code >= 500)
    return isinstance(error, (APIConnectionError, IncompleteStreamError))


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
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(transient),
            stop=stop_after_attempt(policy.retries + 1),
            wait=wait_exponential(multiplier=policy.base_delay_ms / 1000, max=policy.max_delay_ms / 1000),
            before_sleep=before_sleep,
            reraise=True,
        ):
            with attempt:
                return await stream_reply(self, on_delta=on_delta)
    except (OpenAIError, IncompleteStreamError) as error:
        raise RuntimeError(f"U chat request failed: {error}") from error
