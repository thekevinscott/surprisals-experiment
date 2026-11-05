import json

from ....run import Run
from ....turn import Turn
from ....advice import Advice
from ....utils.write import write


async def score_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    advice = Advice((turn.u_dir / "advice.txt").read_bytes().decode("utf-8"), config.advice_measure, config.output)
    await advice.score(on_delta=run.on_delta)
    write(turn.attempt_dir / "metadata.json",
          json.dumps({"advice": str(advice.directory.relative_to(config.output))}, indent=2) + "\n")
