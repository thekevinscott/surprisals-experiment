import json
from functools import partial

from surprisals_experiment.prompt import Prompt

from ....advice import Advice
from ....run import Run
from ....turn import Turn
from ....utils.u_chat.stream_reply.errors import OutputTokenLimitError
from ....utils.write import write
from .prepare_flush import prepare_flush
from .render_code import render_code
from .turn_line import turn_line


FAILED = Prompt("u/failed.txt")


async def write_advice(run: Run, turn: Turn) -> None:
    assert run.u_chat is not None
    config = turn.config
    content = await turn_line(run, turn)
    if not any(entry["role"] == "user" for entry in run.u_chat.entries()):
        content += "\n" + await prepare_flush(turn, run.problem, run.database)
    elif turn.position:
        previous = Turn(config, turn.position - 1, turn.window, turn.fork)
        metadata = json.loads((previous.attempt_dir / "metadata.json").read_text())
        if metadata["advice"] is not None:
            advice = Advice.load(config.output, metadata["advice"], config.advice_measure)
            content += "\n" + advice.measurement + "\n" + await render_code(
                config, run.database, str(previous.attempt_dir.relative_to(config.output)),
            )
        else:
            content += "\n" + FAILED(error=metadata["error"])
    messages = [{"role": "user", "content": content}]
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
    with run.database.dirsql.lock:
        advice = Advice(config.output, text, config.advice_measure)
        reply = run.u_chat.entries()[-1]
        # Older completed replies have no request identity; do not reconstruct one.
        request_metadata = {key: reply[key] for key in ("u_messages", "u_request_sha256") if key in reply}
        write(
            turn.attempt_dir / "metadata.json",
            json.dumps(
                {"advice": advice.id, **request_metadata}, indent=2
            )
            + "\n",
        )
