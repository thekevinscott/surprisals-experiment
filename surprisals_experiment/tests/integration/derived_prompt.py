from run_database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.run_experiment.actions.write_advice.prepare_flush import prepare_flush


async def derived_prompt(config):
    return await prepare_flush(config, QuestionDatabase(config.problem_dir), ExperimentDatabase(config.output))
