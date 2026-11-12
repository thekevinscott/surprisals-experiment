"""One U conversation, without agent tools."""

from dataclasses import dataclass, field
from pathlib import Path

from openai import AsyncOpenAI

from .reply import reply
from .prompt import prompt
from .record import record


@dataclass
class ChatSession:
    client: AsyncOpenAI
    model: str
    thinking: str
    provider: str
    transcript: Path
    messages: list[dict] = field(default_factory=list)

    reply = reply
    prompt = prompt
    record = record
