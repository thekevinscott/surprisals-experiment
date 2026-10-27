"""Retry transient chat failures, including failures after streaming starts."""

import asyncio

import httpx2
from openai import APIConnectionError, APIStatusError, OpenAIError

from .stream_reply import IncompleteStreamError, stream_reply


async def reply(self, *, on_delta=None) -> str:
    history_length = len(self.messages)
    for attempt in range(self.retry_policy.retries + 1):
        try:
            return await stream_reply(self, on_delta=on_delta)
        except (OpenAIError, httpx2.TransportError, IncompleteStreamError) as error:
            transient = isinstance(error, (APIConnectionError, httpx2.TransportError, IncompleteStreamError))
            if isinstance(error, APIStatusError):
                transient = error.status_code == 429 or error.status_code >= 500
            if not transient or attempt == self.retry_policy.retries:
                raise RuntimeError(f"U chat request failed: {error}") from error
            # Keep failed partial output on disk, but retry the original conversation.
            del self.messages[history_length:]
            delay = self.retry_policy.delay(attempt + 1)
            if on_delta is not None:
                on_delta("retry", f"{attempt + 1}/{self.retry_policy.retries} in {delay:g}s: {error}\n")
            await asyncio.sleep(delay)
