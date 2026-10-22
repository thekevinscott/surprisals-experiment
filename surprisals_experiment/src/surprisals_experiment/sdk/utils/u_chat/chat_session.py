"""One persistent U conversation, without agent tools."""

from dataclasses import dataclass, field
from pathlib import Path

from openai import AsyncOpenAI

from .prompt import prompt
from .record import record


@dataclass
class ChatSession:
    client: AsyncOpenAI
    model: str
    thinking: str
    solutions: Path
    transcript: Path
    messages: list[dict] = field(default_factory=list)

    prompt = prompt
    record = record
