from ....fork import Fork
from ....run import Run
from ....turn import Turn
from ...actions.write_result import read_progress
from .read_fork import read_fork


async def state(run: Run, fork: Fork) -> str:
    row = await read_fork(run, fork)
    if row["pending"]:
        return "turn_pending"
    result, _ = await read_progress(run, Turn(fork.config, row["latest"], fork.window, fork.position))
    if result["stale"] >= fork.config.max_turns_without_improvement:
        return "fork_done"
    if fork.config.max_u_turns is not None and row["turns"] >= fork.config.max_u_turns:
        return "fork_done"
    return "turn_pending"
