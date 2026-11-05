from ....run import Run
from ....turn import Turn
from ....advice import Advice
from ....utils.write import write
from ...prepare_flush import prepare_flush


async def write_advice(run: Run, turn: Turn) -> None:
    config = turn.config
    prompt = await prepare_flush(config, run.problem, run.database)
    write(turn.u_dir / "advice.txt", (await run.u_chat.prompt(prompt, on_delta=run.on_delta)).encode("utf-8"))
    advice = Advice(turn.u_dir / "advice.txt", config.advice_measure, config.output)
    advice.save()
