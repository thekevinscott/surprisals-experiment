import json
from functools import partial

from openai import BadRequestError

from surprisals_experiment.prompt import PROMPTS
from surprisals_experiment.retry_policy.constants import DELAYS

from ....advice import Advice
from ....run import Run
from ....turn import Turn
from ....utils.append import append

REJECTED = (PROMPTS / "u/rejected.txt").read_text()


async def score_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    advice = Advice(turn.u_dir / "advice.txt", config.advice_measure, config.output)
    try:
        await advice.score(
            on_delta=partial(run.on_delta, str(turn.u_dir.relative_to(config.output)))
            if run.on_delta
            else None
        )
    except BadRequestError as error:
        rejected = turn.u_dir / "rejected"
        rejections = len(list(rejected.glob("*.txt"))) if rejected.exists() else 0
        if "context limit" not in str(error) or rejections == len(DELAYS):
            raise
        (turn.attempt_dir / "metadata.json").unlink()
        rejected.mkdir(exist_ok=True)
        (turn.u_dir / "advice.txt").rename(rejected / f"{rejections}.txt")
        append(run.u_chat.transcript, json.dumps({
            "role": "user", "content": REJECTED.format(error=error),
        }, ensure_ascii=False) + "\n")
