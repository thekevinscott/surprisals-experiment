"""Append one message to U's conversation and to its transcript."""

import json

from ..write import write


def record(self, message: dict) -> None:
    previous = self.transcript.read_text() if self.transcript.exists() else ''
    write(self.transcript, previous + json.dumps(message, ensure_ascii=False) + '\n')
    self.messages.append(message)
