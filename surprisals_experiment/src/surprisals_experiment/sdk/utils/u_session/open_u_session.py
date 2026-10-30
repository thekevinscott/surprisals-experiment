"""Open a persistent chat or agent U session with temporary source snapshots."""

import sys

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from openai import AsyncOpenAI

from surprisals_experiment.prompt import PROMPTS, Prompt
from ..u_agent import UAgent
from ..u_chat import ChatSession
from ..botbox_session import botbox_session
from .u_session import USession

RESOURCES = Path(str(files("surprisals_experiment")))
SYSTEM = Prompt(PROMPTS / "u/system.txt")
CONTEXTS = {name: Prompt(PROMPTS / f"u/{name}/context.txt") for name in ("agent", "chat", "flush")}


@asynccontextmanager
async def open_u_session(config) -> AsyncGenerator[USession | ChatSession]:
    with TemporaryDirectory(prefix="surprisals-u-solutions-") as temporary:
        workspace = Path(temporary)
        prompt = SYSTEM(
            measure_wording=config.advice_measure.wording,
            implementation_access=CONTEXTS[config.u_context](),
            t_samples=config.t_samples,
            max_turns_without_improvement=config.max_turns_without_improvement,
        )
        solutions = workspace / "solutions"
        solutions.mkdir()
        if config.u_mode == "chat":
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
            return
        system_prompt = workspace / "u.txt"
        system_prompt.write_text(prompt)
        agent = UAgent(provider="openrouter", model=config.u_model,
                       api_key=config.api_key.get_secret_value(), thinking=config.u_thinking)
        pi_session = None
        try:
            async with botbox_session(
                agent, dockerfile=RESOURCES / "docker/U/Dockerfile",
                mounts=[(system_prompt, "/u-config/u.txt", "ro"), (solutions, "/solutions", "ro")],
                workdir="/solutions", output=config.u_dir,
            ) as pi_session:
                yield USession(pi_session, solutions)
        finally:
            if pi_session is not None and pi_session.result is not None:
                print((config.u_dir / "stderr.txt").read_text(), file=sys.stderr, end="", flush=True)
