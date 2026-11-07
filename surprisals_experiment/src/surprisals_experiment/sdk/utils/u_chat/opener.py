"""Open a chat U session."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from openai import AsyncOpenAI

from surprisals_experiment.prompt import Prompt
from .chat_session import ChatSession
from .record.restore import restore
from ..write import write

SYSTEM = Prompt("u/system.txt")
CONTEXT = Prompt("u/flush/context.txt")


@asynccontextmanager
async def open_u_chat(config, *, transcripts=None) -> AsyncGenerator[ChatSession]:
    prompt = SYSTEM(
        measure_wording=config.advice_measure.wording,
        implementation_access=CONTEXT(),
        t_samples=config.t_samples,
    )
    async with AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=config.api_key.get_secret_value(),
        max_retries=0,
    ) as client:
        transcripts = config.u_transcripts if transcripts is None else transcripts
        transcripts.mkdir(parents=True, exist_ok=True)
        u_chat = ChatSession(
            client, config.u_model, config.u_thinking, config.u_provider,
            transcripts / "messages.jsonl",
        )
        if u_chat.transcript.exists():
            lines = u_chat.transcript.read_bytes().splitlines(keepends=True)
            for index, line in enumerate(lines):
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    if index != len(lines) - 1:
                        raise
                    # Remove a torn suffix so the next append starts a valid line.
                    write(u_chat.transcript, b"".join(lines[:index]))
                    break
                restore(u_chat, entry)
        else:
            u_chat.record({"role": "system", "content": prompt})
        yield u_chat
