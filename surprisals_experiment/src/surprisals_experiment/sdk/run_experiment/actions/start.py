from ...run import Run
from ...utils.write import write


async def start(run: Run) -> None:
    config = run.config
    config.save_settings()
    write(config.window_dir / "window.json", "{}\n")
    write(config.fork_dir / "fork.json", "{}\n")


