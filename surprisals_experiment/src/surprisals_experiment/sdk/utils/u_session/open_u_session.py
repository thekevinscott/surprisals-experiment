"""Open U's isolated Pi session and retain its transcripts and proxy log."""

import sys

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from ..u_agent import UAgent
from ..botbox_session import botbox_session
from ..run_sync import run_sync
from ..transcripts import save_transcripts
from .u_session import USession

RESOURCES = Path(str(files("surprisals_experiment")))


@asynccontextmanager
async def open_u_session(config) -> AsyncGenerator[USession]:
    agent = UAgent(provider="openrouter", model=config.u_model,
                   api_key=config.api_key.get_secret_value(), thinking=config.u_thinking)
    with TemporaryDirectory(prefix="surprisals-u-solutions-") as temporary:
        workspace = Path(temporary)
        system_prompt = workspace / "u.txt"
        system_prompt.write_text((RESOURCES / "prompts/u.txt").read_text().format(
            max_chars=config.u_advice_max_chars or "Infinity",
        ))
        solutions = workspace / "solutions"
        solutions.mkdir()
        async with botbox_session(
            agent, dockerfile=RESOURCES / "docker/U/Dockerfile",
            mounts=[(system_prompt, "/u-config/u.txt", "ro"), (solutions, "/solutions", "ro")],
            workdir="/solutions",
        ) as pi_session:
            try:
                yield USession(pi_session, solutions)
            finally:
                result = await run_sync(pi_session.close)
                print(result.stderr, file=sys.stderr, end="", flush=True)
                save_transcripts(result.transcript, config.u_transcripts)
                config.u_proxy_log.parent.mkdir(parents=True, exist_ok=True)
                config.u_proxy_log.write_text(result.proxy)
