"""Stream a chat reply and retain its complete message, including reasoning."""

import json
from datetime import UTC, datetime

from openai import LengthFinishReasonError

from ..output_limit_message import output_limit_message


class IncompleteStreamError(RuntimeError):
    """A stream ended before its terminal completion event."""


class OutputTokenLimitError(RuntimeError):
    """U exhausted its output budget without completing its advice."""


def output_limit_error(completion):
    usage = completion.usage
    details = usage.completion_tokens_details if usage is not None else None
    return OutputTokenLimitError(output_limit_message(
        usage.completion_tokens if usage is not None else None,
        details.reasoning_tokens if details is not None else None,
    ))


async def stream_reply(self, *, on_delta=None) -> str:
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
                raise IncompleteStreamError("U chat returned no advice")
            completion = await stream.get_final_completion()
    except LengthFinishReasonError as error:
        snapshot = error.completion
        raise output_limit_error(snapshot) from error
    finally:
        usage = snapshot.usage if snapshot is not None else None
        with self.transcript.with_name("usage.jsonl").open("a") as log:
            log.write(json.dumps({
                "timestamp": datetime.now(UTC).isoformat(),
                "completion_id": snapshot.id if snapshot is not None else None,
                "usage": usage.model_dump(exclude_unset=True) if usage is not None else None,
            }) + "\n")
        if snapshot is not None and snapshot.choices:
            message = snapshot.choices[0].message.model_dump(exclude_none=True)
            message.pop("parsed", None)
            message["role"] = "assistant"
            self.record(message)
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        raise output_limit_error(completion)
    if choice.finish_reason is None:
        raise IncompleteStreamError("U chat stream ended before completion")
    if choice.finish_reason != "stop" or not choice.message.content:
        raise RuntimeError(f"U chat did not produce complete advice ({choice.finish_reason})")
    return choice.message.content
