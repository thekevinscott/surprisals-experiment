"""Open a persistent chat or agent U session with temporary source snapshots."""

import sys

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from openai import AsyncOpenAI

from ..u_agent import UAgent
from ..u_chat import ChatSession
from ..botbox_session import botbox_session
from ..transcripts import save_transcripts
from .u_session import USession

RESOURCES = Path(str(files("surprisals_experiment")))


@asynccontextmanager
async def open_u_session(config) -> AsyncGenerator[USession | ChatSession]:
    with TemporaryDirectory(prefix="surprisals-u-solutions-") as temporary:
        workspace = Path(temporary)
        prompt = (RESOURCES / "prompts/u.txt").read_text().format(
            implementation_access=(RESOURCES / f"prompts/u_context_{config.u_mode}.txt").read_text(),
            t_samples=config.t_samples,
            max_turns_without_improvement=config.max_turns_without_improvement,
        )
        solutions = workspace / "solutions"
        solutions.mkdir()
        if config.u_mode == "chat":
            async with AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1", api_key=config.api_key.get_secret_value(),
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
                workdir="/solutions",
            ) as pi_session:
                yield USession(pi_session, solutions)
        finally:
            if pi_session is not None and pi_session.result is not None:
                result = pi_session.result
                print(result.stderr, file=sys.stderr, end="", flush=True)
                save_transcripts(result.transcript, config.u_transcripts)
                config.u_proxy_log.parent.mkdir(parents=True, exist_ok=True)
                config.u_proxy_log.write_text(result.proxy)
