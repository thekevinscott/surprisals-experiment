from pathlib import Path

from state_machine import state_machine

from ....run import Run
from ....turn import Turn

STATE = Path(__file__).with_name("state.sql")


async def state(run: Run, turn: Turn) -> str:
    row, = await run.database.query(STATE, **turn.params, samples=turn.config.t_samples)
    return row["state"]


async def run_turn(run: Run, turn: Turn) -> None:
    await state_machine(state, run.actions, run, turn)
