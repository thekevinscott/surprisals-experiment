from .....fork import Fork
from .....run import Run
from .....turn import Turn
from ...run_turn import run_turn
from .read_fork import read_fork


async def turn_pending(run: Run, fork: Fork, turn_cap: int | None = None) -> None:
    row = await read_fork(run, fork)
    position = row["latest"] if row["pending"] else row["completed"]
    turn = Turn(fork.config, position, fork.window, fork.position)
    await run_turn(run, turn)
