from surprisals_experiment.prompt import Prompt

from ....run import Run
from ....turn import Turn
from ...state.read_window import IMPROVEMENT, read_window

TURN = Prompt("u/turn.txt")


async def turn_line(run: Run, turn: Turn) -> str:
    row = await read_window(run)
    best = row["previous"] if turn.window else None
    target = best * (1 - IMPROVEMENT) if best is not None else None
    if best is not None:
        if turn.config.cap_strategy == "characters":
            best, target = str(round(best)), str(round(target))
        else:
            best, target = f"{best:.1f}", f"{target:.1f}"
    return TURN(
        turn=turn.position + 1,
        turns=turn.config.max_u_turns,
        best=best,
        target=target,
        improvement=f"{IMPROVEMENT:.0%}",
    )
