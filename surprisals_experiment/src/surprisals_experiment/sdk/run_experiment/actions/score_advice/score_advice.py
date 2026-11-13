import json
from functools import partial

from openai import BadRequestError

from surprisals_experiment.prompt import PROMPTS
from surprisals_experiment.retry_policy.constants import DELAYS

from ....run import Run
from ....turn import Turn
from ....utils.append import append

REJECTED = (PROMPTS / "u/rejected.txt").read_text()


async def score_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    advice = turn.advice
    try:
        await advice.score(
            on_delta=partial(run.on_delta, str(turn.u_dir.relative_to(config.output)))
            if run.on_delta
            else None
        )
    except BadRequestError as error:
        assert run.u_chat is not None
        rejections = 0
        for entry in reversed(run.u_chat.entries()):
            if "_attempt" in entry:
                break
            if entry["role"] == "user" and entry["content"] == REJECTED:
                rejections += 1
        if "context limit" not in str(error) or rejections == len(DELAYS):
            raise
        (turn.attempt_dir / "metadata.json").unlink()
        append(run.u_chat.transcript, json.dumps({
            "role": "user", "content": REJECTED,
        }, ensure_ascii=False) + "\n")
    else:
        if run.u_chat is not None and run.u_chat.entries()[-1]["role"] == "assistant":
            append(run.u_chat.transcript, json.dumps({
                "role": "user", "content": advice.measurement,
            }, ensure_ascii=False) + "\n")
