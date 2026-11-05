from ....run import Run
from ....window import Window
from ....utils.write import write
from ...state.run_window import run_window
from ...state.run_window.machine import state as window_state
from ...state.read_window import read_window


async def window_pending(run: Run) -> None:
    row = await read_window(run)
    window = Window(run.config, row["position"])
    if await window_state(run, window) == "window_done":
        window = Window(run.config, window.position + 1)
    write(window.window_dir / "window.json", "{}\n")
    write(window.window_dir / "forks/0/fork.json", "{}\n")
    await run_window(run, window)
