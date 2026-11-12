"""Send U the conversation, appending to the transcript only what it does not hold yet."""


async def prompt(self, messages: list[dict], *, on_delta=None) -> str:
    sent = self.messages
    if sent and sent[:-1] == messages and sent[-1]["role"] == "assistant":
        return sent[-1]["content"]
    if messages[:len(sent)] != sent:
        diverged = len(list(self.transcript.parent.glob("messages.diverged-*.jsonl")))
        moved = self.transcript.with_name(f"messages.diverged-{diverged}.jsonl")
        self.transcript.rename(moved)
        if on_delta is not None:
            on_delta("warning", f"U transcript diverged from the request; moved to {moved}\n")
        self.messages = []
    for message in messages[len(self.messages):]:
        self.record(message)
    text = await self.reply(on_delta=on_delta)
    self.record({"role": "assistant", "content": text})
    return text
