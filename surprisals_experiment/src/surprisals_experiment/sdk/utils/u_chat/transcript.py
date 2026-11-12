"""Read the conversation; every line is sent to U as written."""

import json


def entries(self) -> list[dict]:
    return [json.loads(line) for line in self.transcript.read_text().splitlines()]


def request_messages(self) -> list[dict]:
    # Reasoning, timestamp, completion_id and usage stay on disk only.
    return [{key: entry[key] for key in ("role", "content")} for entry in self.entries()]
