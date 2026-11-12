"""One U conversation, without agent tools."""

from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI

from .prompt import prompt
from .reply import reply
from .transcript import entries, request_messages


@dataclass
class ChatSession:
    client: AsyncOpenAI
    model: str
    thinking: str
    provider: str
    transcript: Path
    reply = reply
    prompt = prompt
    entries = entries
    request_messages = request_messages
