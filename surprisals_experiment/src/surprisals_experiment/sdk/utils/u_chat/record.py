"""Persist each message when it enters the conversation."""

import json


def record(self, message: dict) -> None:
    self.messages.append(message)
    with self.transcript.open("a") as transcript:
        transcript.write(json.dumps(message, ensure_ascii=False) + "\n")
