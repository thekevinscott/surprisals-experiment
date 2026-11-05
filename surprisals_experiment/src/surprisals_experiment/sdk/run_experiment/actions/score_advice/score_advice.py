from ....run import Run
from ....turn import Turn
from ....advice import Advice


async def score_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    advice = Advice(turn.u_dir / "advice.txt", config.advice_measure, config.output)
    await advice.score(on_delta=run.on_delta)
