from state_machine import state_machine

from ....run import Run
from ....window import Window
from .state import state


async def run_window(run: Run, window: Window) -> None:
    await state_machine(state, run.actions, run, window)
