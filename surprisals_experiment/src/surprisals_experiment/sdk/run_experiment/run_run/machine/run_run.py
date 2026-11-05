from state_machine import state_machine

from ....run import Run
from .state import state


async def run_run(run: Run) -> None:
    await state_machine(state, run.actions, run)
