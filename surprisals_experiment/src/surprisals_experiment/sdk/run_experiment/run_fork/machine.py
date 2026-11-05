from pathlib import Path

from state_machine import state_machine

from ...fork import Fork
from ...run import Run
from ...turn import Turn
from ..actions.write_result import read_progress
from ..run_turn import run_turn

STATE = Path(__file__).with_name("state.sql")


async def read_fork(run: Run, fork: Fork) -> dict:
    row, = await run.database.query(STATE, **fork.params, samples=fork.config.t_samples)
    return row


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


async def turn_pending(run: Run, fork: Fork) -> None:
    row = await read_fork(run, fork)
    position = row["latest"] if row["pending"] else row["completed"]
    turn = Turn(fork.config, position, fork.window, fork.position)
    await run_turn(run, turn)
    await run.actions["feedback"](run, turn)


async def run_fork(run: Run, fork: Fork) -> None:
    await state_machine(state, run.actions, run, fork)
