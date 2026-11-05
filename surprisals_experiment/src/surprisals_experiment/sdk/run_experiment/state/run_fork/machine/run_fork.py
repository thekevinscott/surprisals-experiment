from state_machine import state_machine

from .....fork import Fork
from .....run import Run
from .state import state


async def run_fork(run: Run, fork: Fork) -> None:
    await state_machine(state, run.actions, run, fork)
