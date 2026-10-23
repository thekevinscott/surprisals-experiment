"""Compact accumulated history when needed, then issue the pending request."""

import json


async def prompt(self, text: str, *, on_delta=None) -> str:
    projected_chars = sum(len(json.dumps(message, ensure_ascii=False)) for message in self.messages) + len(text)
    if self.compact_chars and len(self.messages) > 1 and projected_chars > self.compact_chars:
        await self.compact(on_delta=on_delta)
    self.record({"role": "user", "content": text})
    return await self.reply(on_delta=on_delta)
