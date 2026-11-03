"""Resume a pending turn, or compact history before issuing a new request."""


async def prompt(self, text: str, *, on_delta=None) -> str:
    if self.attempt is not None and self.turn_attempt == self.attempt:
        if self.turn_reply is not None:
            return self.turn_reply
        return await self.reply(on_delta=on_delta)
    if self.flush:
        self.messages = self.messages[:1]
    projected_chars = sum(
        len(message.get('content') or '') + len(message.get('reasoning') or '')
        for message in self.messages
    ) + len(text)
    if self.compacting or (self.compact_chars and len(self.messages) > 1 and projected_chars > self.compact_chars):
        await self.compact(on_delta=on_delta)
    self.record({'role': 'user', 'content': text}, attempt=self.attempt, reset=self.flush)
    return await self.reply(on_delta=on_delta)
