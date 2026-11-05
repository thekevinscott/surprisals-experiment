from state_machine import state_machine

from ...fork import Fork
from ...run import Run
from ...window import Window
from ..run_fork import fork_state, run_fork


async def state(run: Run, window: Window) -> str:
    fork = Fork(window.config, window.position, 0)
    return "window_done" if await fork_state(run, fork) == "fork_done" else "fork_pending"


async def fork_pending(run: Run, window: Window) -> None:
    await run_fork(run, Fork(window.config, window.position, 0))


async def run_window(run: Run, window: Window) -> None:
    await state_machine(state, run.actions, run, window)
