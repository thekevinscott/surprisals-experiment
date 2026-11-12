"""Read the conversation, retaining raw replies only in the transcript."""

import json


def entries(self) -> list[dict]:
    return [json.loads(line) for line in self.transcript.read_text().splitlines()]


def request_messages(self) -> list[dict]:
    messages = []
    reply = None
    for entry in self.entries():
        if entry.get("_complete") is False:
            continue
        # Reply reasoning and timestamp/completion_id/usage remain on disk only.
        message = {key: entry[key] for key in ("role", "content")}
        if message["role"] == "assistant":
            # Only the latest successful reply has T feedback. Earlier replies
            # may have been rejected by the scorer or interrupted before saving.
            reply = message
        else:
            if reply is not None:
                messages.append(reply)
                reply = None
            messages.append(message)
    return messages
