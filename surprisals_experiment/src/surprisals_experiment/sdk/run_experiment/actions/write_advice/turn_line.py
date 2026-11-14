from math import floor

from surprisals_experiment.prompt import Prompt

from ....run import Run
from ....turn import Turn
from ...state.read_window import IMPROVEMENT, read_window

TURN = Prompt("u/turn.txt")


async def turn_line(run: Run, turn: Turn) -> str:
    row = await read_window(run)
    best = row["previous"] if turn.window else None
    target = None
    if best is not None:
        scale = 1 if turn.config.cap_strategy == "characters" else 10
        target = floor(best * (1 - IMPROVEMENT) * scale) / scale
        if turn.config.cap_strategy == "characters":
            best, target = str(round(best)), str(int(target))
        else:
            best, target = f"{best:.1f}", f"{target:.1f}"
    return TURN(
        turn=turn.position + 1,
        turns=turn.config.fork_turns + turn.config.window_solo_turns,
        best=best,
        target=target,
        improvement=f"{IMPROVEMENT:.0%}",
    )
