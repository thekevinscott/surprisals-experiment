from state_machine import state_machine

from .....run import Run
from .....window import Window
from .state import state
from .....utils.write import write


async def run_window(run: Run, window: Window) -> None:
    write(window.window_dir / "window.json", "{}\n")
    await state_machine(state, run.actions, run, window)
