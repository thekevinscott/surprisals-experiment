from .....fork import Fork
from .....run import Run
from .read_fork import read_fork


async def state(run: Run, fork: Fork, turn_cap: int | None = None) -> str:
    row = await read_fork(run, fork)
    if turn_cap is not None and row["completed"] >= turn_cap:
        return "fork_done"
    if row["pending"]:
        return "turn_pending"
    if fork.config.max_u_turns is not None and row["turns"] >= fork.config.max_u_turns:
        return "fork_done"
    return "turn_pending"
