from functools import partial

from ....advice import Advice
from ....run import Run
from ....turn import Turn


async def score_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    advice = Advice(turn.u_dir / "advice.txt", config.advice_measure, config.output)
    await advice.score(
        on_delta=partial(run.on_delta, str(turn.u_dir.relative_to(config.output)))
        if run.on_delta
        else None
    )
