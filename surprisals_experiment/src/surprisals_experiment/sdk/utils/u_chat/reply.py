"""Make one chat request; the experiment state selects the next step."""

from .stream_reply import stream_reply


async def reply(self, *, on_delta=None) -> str:
    return await stream_reply(self, on_delta=on_delta)
