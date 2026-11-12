"""Run T on U's advice in a fresh botbox workspace."""

import json
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
    """Run T, save its reply as main.py, keep its logs, and return its exit."""
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
        result = await botbox_run(
            agent,
            agent.command(),
            dockerfile=Path(__file__).parents[1] / "docker/Dockerfile.t",
            mounts=[(output, "/solution", "rw"), (advice_dir, "/advice", "ro")],
            workdir="/solution",
            output=logs,
            on_event=agent.receive,
        )
    if result.exit_code == -1:
        return result
    # Read the completed event from disk: the live follower may stop before its last poll.
    with (logs / "stdout.txt").open(encoding="utf-8") as stdout:
        for line in stdout:
            event = json.loads(line)
            if event["type"] == "agent_end":
                for message in event["messages"]:
                    if message["role"] == "assistant" and message["stopReason"] in ("stop", "length"):
                        program = "".join(
                            block["text"] for block in message["content"] if block["type"] == "text"
                        )
                        (output / "main.py").write_text(program, encoding="utf-8")
    return result
