"""Run one real fork for adapter tests; full-window behavior lives in test_state_machine."""

from surprisals_experiment.sdk.database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.run_experiment.run_experiment import drive_fork
from surprisals_experiment.sdk.run_experiment.actions.write_result import write_result
from surprisals_experiment.sdk.utils.write import write


async def run_fork(config, *, on_delta, on_t_delta=None):
    config.save_settings()
    write(config.window_dir / 'window.json', '{}')
    write(config.fork_dir / 'fork.json', '{}')
    database = ExperimentDatabase(config.output)
    await drive_fork(config.at(window=0, fork=0, turn=10), database, QuestionDatabase(config.problem_dir),
                     on_delta=on_delta, on_t_delta=on_t_delta)
    solution = await write_result(config, database)
    if solution is None:
        write(config.error_file, 'No passing solution\n')
    return solution
