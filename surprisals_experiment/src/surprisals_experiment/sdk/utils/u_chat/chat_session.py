"""One persistent U conversation, without agent tools."""

from dataclasses import dataclass, field
from pathlib import Path

from openai import AsyncOpenAI
from surprisals_experiment.retry_policy import RetryPolicy

from .compact import compact
from .reply import reply
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

    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    compact_chars: int = 400000
    question: str = ""
    best_advice: str | None = None
    best_length: int | None = None
    turns_without_improvement: int = 0

    compact = compact
    reply = reply
    prompt = prompt
    record = record
