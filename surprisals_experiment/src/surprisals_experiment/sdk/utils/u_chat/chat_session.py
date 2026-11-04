"""U transport and append-only diagnostics; request history is supplied by callers."""

from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI

from .compact import compact
from .reply import reply
from .prompt import prompt
from .record import record


@dataclass
class ChatSession:
    client: AsyncOpenAI
    model: str
    thinking: str
    transcript: Path

    compact = compact
    reply = reply
    prompt = prompt
    record = record
