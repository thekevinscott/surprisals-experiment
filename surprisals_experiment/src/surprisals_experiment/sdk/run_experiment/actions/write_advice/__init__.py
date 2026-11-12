import json
from functools import partial

from ....advice import Advice
from ....run import Run
from ....turn import Turn
from ....utils.u_chat.stream_reply.errors import OutputTokenLimitError
from ....utils.write import write
from .prepare_flush import prepare_flush
from .render_code import render_code
from .system_prompt import system_prompt


async def write_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    system = await system_prompt(run, turn)
    messages = [{"role": "system", "content": system}]
    if not any(entry["role"] == "user" for entry in run.u_chat.entries()):
        messages.append({"role": "user", "content": await prepare_flush(turn, run.problem, run.database)})
    elif turn.position:
        previous = Turn(config, turn.position - 1, turn.window, turn.fork)
        metadata = json.loads((previous.attempt_dir / "metadata.json").read_text())
        if metadata["advice"] is not None:
            messages.append({"role": "user", "content": await render_code(
                config, run.database, str(previous.attempt_dir.relative_to(config.output)),
            )})
    try:
        text = await run.u_chat.prompt(
            messages, attempt=turn.position,
            on_delta=partial(run.on_delta, str(turn.u_dir.relative_to(config.output)))
            if run.on_delta
            else None,
        )
    except OutputTokenLimitError as error:
        write(
            turn.attempt_dir / "metadata.json",
            json.dumps({"advice": None, "error": str(error)}, indent=2) + "\n",
        )
        return
    write(turn.u_dir / "advice.txt", text.encode("utf-8"))
    advice = Advice(turn.u_dir / "advice.txt", config.advice_measure, config.output)
    with run.database.dirsql.lock:
        advice.save()
        write(
            turn.attempt_dir / "metadata.json",
            json.dumps(
                {"advice": str(advice.directory.relative_to(config.output))}, indent=2
            )
            + "\n",
        )
