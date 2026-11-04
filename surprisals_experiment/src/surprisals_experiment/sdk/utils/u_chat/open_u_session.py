"""Open U transport and its append-only transcript."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from openai import AsyncOpenAI

from surprisals_experiment.prompt import Prompt
from .chat_session import ChatSession

SYSTEM = Prompt("u/system.txt")
CONTEXTS = {name: Prompt(f"u/{name}/context.txt") for name in ("chat", "flush")}


def system_message(config):
    return {"role": "system", "content": SYSTEM(
        measure_wording=config.advice_measure.wording,
        implementation_access=CONTEXTS[config.u_context](),
        t_samples=config.t_samples,
        max_turns_without_improvement=config.max_turns_without_improvement,
    )}


@asynccontextmanager
async def open_u_session(config) -> AsyncGenerator[ChatSession]:
    async with AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=config.api_key.get_secret_value(),
        max_retries=0,
    ) as client:
        config.u_transcripts.mkdir(parents=True, exist_ok=True)
        u_session = ChatSession(
            client, config.u_model, config.u_thinking,
            config.u_transcripts / "messages.jsonl",
        )
        u_session.record(system_message(config))
        yield u_session
