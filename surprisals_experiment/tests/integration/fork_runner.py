"""Exercise one fork's adapters; full-window behavior is tested separately."""

from surprisals_experiment.sdk.database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.run_experiment.run_experiment import drive_fork
from surprisals_experiment.sdk.run_experiment.actions.write_result import write_result
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.write import write


async def run_fork(config, *, on_delta, on_t_delta=None):
    config.save_settings()
    write(config.window_dir / 'window.json', '{}')
    write(config.fork_dir / 'fork.json', '{}')
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    problem = QuestionDatabase(config.problem_dir)
    limit = config.max_u_turns if config.max_u_turns is not None else 40
    solution = None
    for position in range(limit):
        await drive_fork(config, database, problem, 0, 0, position, position + 1,
                         on_delta=on_delta, on_t_delta=on_t_delta)
        solution, stale = await write_result(Turn(config, position), database)
        if stale >= config.max_turns_without_improvement:
            break
    if solution is None:
        write(config.error_file, 'No passing solution\n')
    return solution
