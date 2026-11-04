"""Append diagnostics without using the transcript as request state."""

import json


def record(self, message: dict) -> None:
    with self.transcript.open('a') as transcript:
        transcript.write(json.dumps(message, ensure_ascii=False) + '\n')
