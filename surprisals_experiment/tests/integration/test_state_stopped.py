"""Stop checks over completed and partial run-folder artifacts."""

import json
from pathlib import Path

import pytest
from advice_artifacts import write_advice

from surprisals_experiment.sdk.database import ExperimentDatabase

SQL = Path(__file__).parents[2] / 'src/surprisals_experiment/sdk/run_experiment/states/stopped.sql'


@pytest.mark.parametrize('scores,passed,cap,max_stale,partial,expected', [
    ([], [], 1, 2, None, False),
    ([10], [True], 1, 2, None, True),
    ([10], [True], 2, 2, None, False),
    ([10, 10], [False, False], -1, 2, None, True),
    ([10, 9], [False, True], -1, 2, None, False),
    ([10, 10, 11], [True, True, True], -1, 2, None, True),
    ([10, 9, 8], [True, False, False], -1, 2, None, True),
    ([10, 10, 9], [True, False, True], -1, 2, None, False),
    ([10, 10], [False, False], 1, 1, 'feedback', False),
    ([10, 10], [False, False], 1, 1, 'generation', False),
    ([10, 10], [False, False], 1, 1, 'samples', False),
])
async def test_stopped(config, scores, passed, cap, max_stale, partial, expected):
    config.fork_dir.mkdir(parents=True)
    (config.window_dir / 'window.json').write_text('{}')
    (config.fork_dir / 'fork.json').write_text('{}')
    for index, (score, success) in enumerate(zip(scores, passed)):
        turn = config.attempt_dir(index)
        turn.mkdir(parents=True)
        write_advice(config, turn, f'advice {index}', score)
        last = index == len(scores) - 1
        if not (last and partial == 'feedback'):
            (turn / 'feedback.txt').write_text('feedback')
        for sample in range(1 if last and partial == 'samples' else 2):
            folder = config.t_dir(index, sample)
            folder.mkdir(parents=True)
            if not (last and partial == 'generation'):
                (folder / 'run.json').write_text('{"exit_code": 0}')
            (folder / 'tests.json').write_text(json.dumps({'cases': [{
                'index': 0, 'passed': success, 'status': 'passed' if success else 'wrong_answer',
                'stdout': '', 'stderr': '',
            }]}))
    assert await ExperimentDatabase(config.output).query(
        SQL, samples=2, cap=cap, max_stale=max_stale,
    ) == [{'stopped': int(expected)}]


async def test_unstarted_run_is_not_stopped(config):
    config.output.mkdir()
    assert await ExperimentDatabase(config.output).query(
        SQL, samples=2, cap=0, max_stale=1,
    ) == [{'stopped': 0}]
