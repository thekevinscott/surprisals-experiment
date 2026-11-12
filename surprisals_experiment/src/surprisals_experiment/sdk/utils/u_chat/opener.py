"""Open a chat U session."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from openai import AsyncOpenAI

from surprisals_experiment.config import OPENROUTER_BASE_URL
from surprisals_experiment.prompt import Prompt

from ..append import append
from ..write import write
from .chat_session import ChatSession

SYSTEM = Prompt("u/system.txt")
CONTEXT = Prompt("u/flush/context.txt")


@asynccontextmanager
async def open_u_chat(config, *, transcript=None) -> AsyncGenerator[ChatSession]:
    prompt = SYSTEM(
        measure_wording=config.advice_measure.wording,
        implementation_access=CONTEXT(),
        t_samples=config.t_samples,
    )
    async with AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL, api_key=config.api_key.get_secret_value(),
        max_retries=0,
    ) as client:
        transcript = config.u_transcript if transcript is None else transcript
        transcript.parent.mkdir(parents=True, exist_ok=True)
        u_chat = ChatSession(
            client, config.u_model, config.u_thinking, config.u_provider,
            transcript,
        )
        if u_chat.transcript.exists():
            lines = u_chat.transcript.read_bytes().splitlines(keepends=True)
            for index, line in enumerate(lines):
                try:
                    json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    if index != len(lines) - 1:
                        raise
                    # Remove a torn suffix so the next append starts a valid line.
                    write(u_chat.transcript, b"".join(lines[:index]))
                    break
        else:
            append(u_chat.transcript, json.dumps({"role": "system", "content": prompt}, ensure_ascii=False) + "\n")
        yield u_chat
