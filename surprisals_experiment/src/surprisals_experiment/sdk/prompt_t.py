"""Run T on U's advice in a fresh botbox workspace."""

from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from botbox import RunResult

from surprisals_experiment.config import T_PI_PROVIDER, Config
from surprisals_experiment.prompt import Prompt

from .utils.botbox_run.botbox_run import botbox_run
from .utils.t_agent import TAgent

INSTRUCTIONS = Prompt("t.txt")


async def prompt_t(
    config: Config,
    advice: str,
    *,
    output: Path,
    logs: Path,
    on_delta: Callable[[str, str], None] | None = None,
) -> RunResult:
    """Run T, write its streams, proxy log and transcripts live to `logs`, and return its exit."""
    output.mkdir(parents=True, exist_ok=False)
    agent = TAgent(
        provider=T_PI_PROVIDER,
        model=config.t_model,
        route=config.t_provider,
        api_key=config.api_key.get_secret_value(),
        instructions=INSTRUCTIONS(),
        on_delta=on_delta,
    )
    with TemporaryDirectory() as directory:
        advice_dir = Path(directory)
        (advice_dir / "advice.md").write_bytes(advice.encode("utf-8"))
        return await botbox_run(
            agent,
            agent.command(),
            dockerfile=Path(__file__).parents[1] / "docker/Dockerfile.t",
            mounts=[(output, "/solution", "rw"), (advice_dir, "/advice", "ro")],
            workdir="/solution",
            output=logs,
            on_event=agent.receive,
        )
