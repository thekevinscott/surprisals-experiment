"""Run T on U's advice in a fresh botbox workspace."""

from collections.abc import Callable
from importlib.resources import files
from pathlib import Path

from botbox import RunResult

from surprisals_experiment.config import Config
from surprisals_experiment.prompt import PROMPTS, Prompt
from .utils.t_agent import TAgent
from .utils.botbox_session import botbox_session


RESOURCES = files("surprisals_experiment")
INSTRUCTIONS = Prompt(PROMPTS / "t.txt")


async def prompt_t(config: Config, advice: str, *, output: Path, logs: Path,
             on_delta: Callable[[str, str], None] | None = None) -> RunResult:
    """Run T, write its streams, proxy log and transcripts live to `logs`, and return its exit."""
    output.mkdir(parents=True, exist_ok=False)
    agent = TAgent(
        provider="openrouter", model=config.t_model, api_key=config.api_key.get_secret_value(),
        instructions=INSTRUCTIONS(), on_delta=on_delta,
    )
    async with botbox_session(
        agent, dockerfile=Path(str(RESOURCES.joinpath("docker/Dockerfile.t"))),
        mounts=[(output, "/solution", "rw")], workdir="/solution", output=logs,
    ) as t_session:
        await t_session.message(advice)
    return t_session.result
