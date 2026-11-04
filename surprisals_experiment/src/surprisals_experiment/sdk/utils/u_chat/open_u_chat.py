"""Open a persistent chat U session."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from openai import AsyncOpenAI

from surprisals_experiment.prompt import Prompt
from ...database import QuestionDatabase
from .chat_session import ChatSession
from .record import restore

SYSTEM = Prompt("u/system.txt")
CONTEXTS = {name: Prompt(f"u/{name}/context.txt") for name in ("chat", "flush")}


@asynccontextmanager
async def open_u_chat(config, problem: QuestionDatabase) -> AsyncGenerator[ChatSession]:
    prompt = SYSTEM(
        measure_wording=config.advice_measure.wording,
        implementation_access=CONTEXTS[config.u_context](),
        t_samples=config.t_samples,
        max_turns_without_improvement=config.max_turns_without_improvement,
    )
    async with AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=config.api_key.get_secret_value(),
        max_retries=0,
    ) as client:
        config.u_transcripts.mkdir(parents=True, exist_ok=True)
        u_chat = ChatSession(
            client, config.u_model, config.u_thinking,
            config.u_transcripts / "messages.jsonl",
            compact_chars=config.u_compact_chars, question=await problem.question,
            flush=config.u_flush,
        )
        if u_chat.transcript.exists():
            with u_chat.transcript.open('r+b') as transcript:
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
                    restore(u_chat, entry)
        else:
            u_chat.record({"role": "system", "content": prompt})
        yield u_chat
