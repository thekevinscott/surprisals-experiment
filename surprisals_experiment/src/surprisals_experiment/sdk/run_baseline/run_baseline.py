"""T on the problem's question.txt alone, no U."""

import json
from collections.abc import Callable
from pathlib import Path

from run_database import ExperimentDatabase, QuestionDatabase
from state_machine import Stop

from surprisals_experiment.config import Config

from ..advice import Advice
from ..run import Run
from ..run_experiment.actions.run_tests import run_tests
from ..run_experiment.actions.start import start
from ..run_experiment.actions.write_solutions import write_solutions
from ..run_experiment.actions.write_solutions.produce_code import produce_code
from ..run_experiment.check_test_suite import check_test_suite
from ..turn import Turn
from ..utils.write import write

ALL_PASSED = Path(__file__).with_name("all_passed.sql")

actions = {"solution_missing": produce_code, "untested": run_tests, "sample_done": Stop}


async def run_baseline(config: Config, *, on_t_delta: Callable[[str, str, str], None] | None) -> None:
    problem = QuestionDatabase(config.problem_dir)
    await check_test_suite(config, problem)
    database = ExperimentDatabase(config.output)
    run = Run(config, database, problem, actions, on_t_delta)
    await start(run)
    advice = Advice((config.problem_dir / "question.txt").read_bytes().decode("utf-8"), config.advice_measure, config.output)
    advice.save()
    turn = Turn(config, 0)
    write(turn.attempt_dir / "metadata.json", json.dumps({"advice": str(advice.directory.relative_to(config.output))}) + "\n")
    await database.dirsql.ready()
    await write_solutions(run, turn)
    row, = await database.query(ALL_PASSED)
    write(config.result_file, json.dumps({"samples": config.t_samples, "all_passed": row["all_passed"]}, indent=2) + "\n")
