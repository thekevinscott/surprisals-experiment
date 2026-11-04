"""Request advice using the supplied file-derived conversation."""


async def prompt(self, messages: list[dict], *, on_delta=None) -> dict:
    self.record(messages[-1])
    return await self.reply(messages, on_delta=on_delta)
