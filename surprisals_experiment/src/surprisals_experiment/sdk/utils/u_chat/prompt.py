"""Append new input before making a request from the transcript."""

import json

from ..append import append


async def prompt(self, messages: list[dict], *, attempt=None, on_delta=None) -> str:
    entries = self.entries()
    last_attempt = next((entry["_attempt"] for entry in reversed(entries) if "_attempt" in entry), None)
    if attempt is not None and attempt == last_attempt and entries[-1]["role"] == "assistant":
        return entries[-1]["content"]
    if attempt is None or attempt != last_attempt:
        for index, message in enumerate(messages):
            entry = message | ({"_attempt": attempt} if attempt is not None and index == len(messages) - 1 else {})
            append(self.transcript, json.dumps(entry, ensure_ascii=False) + "\n")
    return await self.reply(on_delta=on_delta)
