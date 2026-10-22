"""Open U's isolated Pi session and retain its transcripts and proxy log."""

import sys

from collections.abc import Generator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from botbox import Botbox

from ..u_agent import UAgent
from ..transcripts import save_transcripts
from .u_session import USession

RESOURCES = Path(str(files("surprisals_experiment")))


@contextmanager
def open_u_session(config) -> Generator[USession]:
    agent = UAgent(provider="openrouter", model=config.u_model,
                   api_key=config.api_key.get_secret_value(), thinking=config.u_thinking)
    with TemporaryDirectory(prefix="surprisals-u-solutions-") as temporary, \
         Botbox(agent, dockerfile=RESOURCES / "docker/U/Dockerfile") as box:
        workspace = Path(temporary)
        system_prompt = workspace / "u.txt"
        system_prompt.write_text((RESOURCES / "prompts/u.txt").read_text().format(
            max_chars=config.u_advice_max_chars or "Infinity",
        ))
        solutions = workspace / "solutions"
        solutions.mkdir()
        pi_session = box.session(mounts=[
            (system_prompt, "/u-config/u.txt", "ro"),
            (solutions, "/solutions", "ro"),
        ], workdir="/solutions")
        try:
            yield USession(pi_session, solutions)
        finally:
            result = pi_session.close()
            print(result.stderr, file=sys.stderr, end="", flush=True)
            save_transcripts(result.transcript, config.u_transcripts)
            config.u_proxy_log.parent.mkdir(parents=True, exist_ok=True)
            config.u_proxy_log.write_text(result.proxy)
