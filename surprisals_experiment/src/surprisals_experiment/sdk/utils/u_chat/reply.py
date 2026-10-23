"""Stream a chat reply and retain its complete message, including reasoning."""

from openai import OpenAIError


async def reply(self, *, on_delta=None) -> str:
    reasoning = {"enabled": False} if self.thinking == "off" else {"effort": self.thinking}
    snapshot = None
    try:
        async with self.client.chat.completions.stream(
            model=self.model, messages=self.messages, extra_body={"reasoning": reasoning},
        ) as stream:
            async for event in stream:
                snapshot = stream.current_completion_snapshot
                if on_delta is not None:
                    if event.type == "content.delta":
                        on_delta("text", event.delta)
                    elif event.type == "chunk":
                        for choice in event.chunk.choices:
                            thinking = getattr(choice.delta, "reasoning", None) or "".join(
                                detail.get("text", detail.get("summary", ""))
                                for detail in (getattr(choice.delta, "reasoning_details", None) or [])
                            )
                            if thinking:
                                on_delta("thinking", thinking)
            if snapshot is None or not snapshot.choices:
                raise RuntimeError("U chat returned no advice")
            completion = await stream.get_final_completion()
    except OpenAIError as error:
        raise RuntimeError(f"U chat request failed: {error}") from error
    finally:
        if snapshot is not None and snapshot.choices:
            message = snapshot.choices[0].message.model_dump(exclude_none=True)
            message.pop("parsed", None)
            message["role"] = "assistant"
            self.record(message)
    choice = completion.choices[0]
    if choice.finish_reason != "stop" or not choice.message.content:
        raise RuntimeError(f"U chat did not produce complete advice ({choice.finish_reason})")
    return choice.message.content
