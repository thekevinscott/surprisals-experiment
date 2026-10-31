"""Open a persistent chat U session with temporary source snapshots."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from openai import AsyncOpenAI

from surprisals_experiment.prompt import Prompt
from ..u_chat import ChatSession

SYSTEM = Prompt("u/system.txt")
CONTEXTS = {name: Prompt(f"u/{name}/context.txt") for name in ("chat", "flush")}


@asynccontextmanager
async def open_u_session(config) -> AsyncGenerator[ChatSession]:
    with TemporaryDirectory(prefix="surprisals-u-solutions-") as temporary:
        prompt = SYSTEM(
            measure_wording=config.advice_measure.wording,
            implementation_access=CONTEXTS[config.u_context](),
            t_samples=config.t_samples,
            max_turns_without_improvement=config.max_turns_without_improvement,
        )
        solutions = Path(temporary) / "solutions"
        solutions.mkdir()
        async with AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=config.api_key.get_secret_value(),
            max_retries=0,
        ) as client:
            config.u_transcripts.mkdir(parents=True, exist_ok=True)
            u_session = ChatSession(
                client, config.u_model, config.u_thinking, solutions,
                config.u_transcripts / "messages.jsonl",
                compact_chars=config.u_compact_chars, question=config.question_file.read_text(),
            )
            u_session.record({"role": "system", "content": prompt})
            yield u_session
