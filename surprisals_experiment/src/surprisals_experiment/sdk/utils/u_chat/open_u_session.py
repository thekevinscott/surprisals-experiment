"""Open a persistent chat U session."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from openai import AsyncOpenAI

from surprisals_experiment.prompt import Prompt
from .chat_session import ChatSession
from .record import restore

SYSTEM = Prompt("u/system.txt")
CONTEXT = Prompt("u/flush/context.txt")


@asynccontextmanager
async def open_u_session(config) -> AsyncGenerator[ChatSession]:
    prompt = SYSTEM(
        measure_wording=config.advice_measure.wording,
        implementation_access=CONTEXT(),
        t_samples=config.t_samples,
        max_turns_without_improvement=config.max_turns_without_improvement,
    )
    async with AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=config.api_key.get_secret_value(),
        max_retries=0,
    ) as client:
        config.u_transcripts.mkdir(parents=True, exist_ok=True)
        u_session = ChatSession(
            client, config.u_model, config.u_thinking,
            config.u_transcripts / "messages.jsonl",
        )
        if u_session.transcript.exists():
            with u_session.transcript.open('r+b') as transcript:
                lines = transcript.readlines()
                for index, line in enumerate(lines):
                    try:
                        entry = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        if index != len(lines) - 1:
                            raise
                        # Remove a torn suffix so the next append starts a valid line.
                        transcript.truncate(sum(map(len, lines[:index])))
                        break
                    restore(u_session, entry)
        else:
            u_session.record({"role": "system", "content": prompt})
        yield u_session
