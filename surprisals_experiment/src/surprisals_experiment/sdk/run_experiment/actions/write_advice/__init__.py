import json
from functools import partial

from ....advice import Advice
from ....run import Run
from ....turn import Turn
from ....utils.write import write
from .prepare_flush import prepare_flush
from .system_prompt import system_prompt


async def write_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    system = await system_prompt(run, turn)
    if run.u_chat.messages[0]["content"] != system:
        run.u_chat.record({"role": "system", "content": system})
    prompt = await prepare_flush(config, run.problem, run.database)
    write(
        turn.u_dir / "advice.txt",
        (
            await run.u_chat.prompt(
                prompt,
                on_delta=partial(
                    run.on_delta, str(turn.u_dir.relative_to(config.output))
                )
                if run.on_delta
                else None,
            )
        ).encode("utf-8"),
    )
    advice = Advice(turn.u_dir / "advice.txt", config.advice_measure, config.output)
    advice.save()
    write(
        turn.attempt_dir / "metadata.json",
        json.dumps(
            {"advice": str(advice.directory.relative_to(config.output))}, indent=2
        )
        + "\n",
    )
