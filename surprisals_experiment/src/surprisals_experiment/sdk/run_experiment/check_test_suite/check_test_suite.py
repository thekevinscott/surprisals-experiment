from pathlib import Path

from surprisals_experiment.config import Config

from run_database import QuestionDatabase

SHAPE = Path(__file__).with_name("shape.sql")


async def check_test_suite(config: Config, problem: QuestionDatabase) -> None:
    shape, = await problem.query(SHAPE)
    if shape["fn_name"]:
        reason = "it has fn_name"
    elif not shape["cases"]:
        reason = "it has no test cases"
    elif shape["non_strings"]:
        reason = "it has non-string inputs or outputs"
    else:
        return
    raise ValueError(f"{config.problem_dir / 'input_output.json'} is not a stdin/stdout test suite: {reason}")
