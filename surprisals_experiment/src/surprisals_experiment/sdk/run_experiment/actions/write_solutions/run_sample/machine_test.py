"""One sample resumes testing without repeating its completed generation."""

import asyncio
import json

import pytest

from advice_artifacts import write_advice
from surprisals_experiment.sdk.database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.run import Run
from surprisals_experiment.sdk.sample import Sample
from surprisals_experiment.sdk.run_experiment.run_experiment import actions
from surprisals_experiment.sdk.run_experiment.actions.write_solutions.run_sample import run_sample

PASS = 'print(int(input()) * 2)\n'


async def setup(config):
    database = ExperimentDatabase(config.output)
    await actions["not_started"](Run(config, database, QuestionDatabase(config.problem_dir), actions))
    await database.dirsql.ready()
    turn = Turn(config, 0)
    turn.attempt_dir.mkdir(parents=True)
    write_advice(config, turn.attempt_dir, 'double', 6)
    return turn, database, QuestionDatabase(config.problem_dir)


async def test_fresh_sample_generates_and_tests(config, botbox_script):
    turn, database, problem = await setup(config)
    botbox_script.solutions.append(PASS)
    await run_sample(Run(config, database, problem, actions), Sample(turn, 0))
    assert len(botbox_script.sessions) == 1
    assert json.loads((turn.t_dir(0) / 'tests.json').read_text())['all_passed']
    await run_sample(Run(config, ExperimentDatabase(config.output), problem, actions), Sample(turn, 0))
    assert len(botbox_script.sessions) == 1


async def test_interrupted_after_generation_resumes_at_testing(config, botbox_script):
    turn, database, problem = await setup(config)
    botbox_script.solutions.append(PASS)

    async def interrupt(*args, **kwargs):
        raise asyncio.CancelledError

    run = Run(config, database, problem, {**actions, "untested": interrupt})
    with pytest.raises(asyncio.CancelledError):
        await run_sample(run, Sample(turn, 0))
    generation = turn.t_dir(0) / 'attempts/0/generation.json'
    source = turn.t_dir(0) / 'attempts/0/src/main.py'
    before = (generation.read_bytes(), generation.stat().st_mtime_ns,
              source.read_bytes(), source.stat().st_mtime_ns)
    assert not (turn.t_dir(0) / 'tests.json').exists()
    await run_sample(Run(config, ExperimentDatabase(config.output), problem, actions), Sample(turn, 0))
    assert len(botbox_script.sessions) == 1
    assert (generation.read_bytes(), generation.stat().st_mtime_ns,
            source.read_bytes(), source.stat().st_mtime_ns) == before
    assert json.loads((turn.t_dir(0) / 'tests.json').read_text())['all_passed']


async def test_other_sample_completion_does_not_skip_requested_sample(config, botbox_script):
    turn, database, problem = await setup(config)
    botbox_script.solutions.extend([PASS, PASS])
    await run_sample(Run(config, database, problem, actions), Sample(turn, 1))
    await run_sample(Run(config, database, problem, actions), Sample(turn, 0))
    assert len(botbox_script.sessions) == 2
    assert (turn.t_dir(0) / 'tests.json').exists()
