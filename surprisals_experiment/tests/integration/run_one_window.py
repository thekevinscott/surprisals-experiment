"""Exercise one window for adapter and turn integration tests; run tests cover orchestration."""

from surprisals_experiment.sdk.database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.run import Run
from surprisals_experiment.sdk.window import Window
from surprisals_experiment.sdk.run_experiment.run_experiment import actions
from surprisals_experiment.sdk.run_experiment.actions.start import start
from surprisals_experiment.sdk.run_experiment.state.run_window import run_window
from surprisals_experiment.sdk.run_experiment.actions.write_result import read_progress, write_result
from surprisals_experiment.sdk.utils.u_chat import open_u_chat
from surprisals_experiment.sdk.utils.write import write


async def run_one_window(config, *, on_delta, on_t_delta=None):
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    async with open_u_chat(config) as u_chat:
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, on_t_delta, u_chat, on_delta)
        if not config.window_dir.exists():
            await start(run)
        await run_window(run, Window(config))
        await write_result(run)
        result, solution = await read_progress(run)
    if solution is None:
        write(config.error_file, f"No passing solution after {result['attempts']} U turns\n")
    return solution
