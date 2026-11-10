"""Resume a pending turn, or start a fresh conversation for a new request."""


async def prompt(self, messages: list[dict], *, on_delta=None) -> str:
    if self.attempt is not None and self.turn_attempt == self.attempt:
        if self.turn_reply is not None:
            return self.turn_reply
        return await self.reply(on_delta=on_delta)
    for index, message in enumerate(messages):
        self.record(message, reset=index == 0, attempt=self.attempt if index == len(messages) - 1 else None)
    return await self.reply(on_delta=on_delta)
