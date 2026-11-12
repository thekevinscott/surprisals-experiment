"""Send U the conversation, appending to the transcript only what it does not hold yet."""


async def prompt(self, messages: list[dict], *, on_delta=None) -> str:
    sent = self.messages
    if sent and sent[:-1] == messages and sent[-1]["role"] == "assistant":
        return sent[-1]["content"]
    if messages[:len(sent)] != sent:
        raise RuntimeError(f"U's transcript {self.transcript} is not the start of the conversation to send")
    for message in messages[len(sent):]:
        self.record(message)
    text = await self.reply(on_delta=on_delta)
    self.record({"role": "assistant", "content": text})
    return text
