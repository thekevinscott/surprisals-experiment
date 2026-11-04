"""Resume a pending turn, or start a fresh conversation for a new request."""


async def prompt(self, text: str, *, on_delta=None) -> str:
    if self.attempt is not None and self.turn_attempt == self.attempt:
        if self.turn_reply is not None:
            return self.turn_reply
        return await self.reply(on_delta=on_delta)
    self.record({'role': 'user', 'content': text}, attempt=self.attempt, reset=True)
    return await self.reply(on_delta=on_delta)
