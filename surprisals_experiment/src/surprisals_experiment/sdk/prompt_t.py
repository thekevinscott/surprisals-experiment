"""Run T on U's advice in a fresh botbox workspace."""

from collections.abc import Callable
from importlib.resources import files
from pathlib import Path

from botbox import Botbox, RunResult

from surprisals_experiment.config import Config
from .utils.t_agent import TAgent


RESOURCES = files("surprisals_experiment")
INSTRUCTIONS = RESOURCES.joinpath("prompts/t.txt").read_text()


def prompt_t(config: Config, advice: str, *, output: Path,
             on_delta: Callable[[str, str], None] | None = None) -> RunResult:
    """Run T, retain its artifacts, and return its process result."""
    output.mkdir(parents=True, exist_ok=False)
    agent = TAgent(
        provider="openrouter", model=config.t_model, api_key=config.api_key.get_secret_value(),
        instructions=INSTRUCTIONS, on_delta=on_delta,
    )
    with Botbox(agent, dockerfile=Path(str(RESOURCES.joinpath("docker/Dockerfile.t")))) as box:
        with box.session(mounts=[(output, "/solution", "rw")], workdir="/solution") as t_session:
            t_session.message(advice)
            result = t_session.close()
    return result
