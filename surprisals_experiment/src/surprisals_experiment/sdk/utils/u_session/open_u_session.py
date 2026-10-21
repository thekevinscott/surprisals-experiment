"""Open U's isolated Pi session and retain its diagnostics."""

from collections.abc import Generator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from botbox import Botbox

from ..u_agent import UAgent
from .save_result import save_result
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
            t_samples=config.t_samples,
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
            save_result(pi_session.close(), config)
