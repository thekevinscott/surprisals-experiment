"""The ordered untested check detects missing test artifacts, not failed tests."""

import json
from pathlib import Path

import pytest

from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.write import write
import surprisals_experiment

CHECK = Path(surprisals_experiment.__file__).parent / 'sdk/run_experiment/states/untested.sql'


def saved_turn(turn):
    write(turn.config.output / f'windows/{turn.window}/window.json', '{}')
    write(turn.attempt_dir.parent.parent / 'fork.json', '{}')
    advice = Advice('double', turn.config.advice_measure, turn.config.output)
    advice.save()
    write(advice.directory / 'advice.json', '{"score": 6}')
    write(turn.attempt_dir / 'metadata.json', json.dumps({
        'advice': str(advice.directory.relative_to(turn.config.output)),
    }))


def saved_test(turn, sample):
    write(turn.t_dir(sample) / 'tests.json', json.dumps({'cases': [{
        'index': 0, 'passed': False, 'status': 'wrong_answer', 'stdout': '', 'stderr': '',
    }]}))


@pytest.mark.parametrize('tested,expected', [
    ([], 1), ([0], 1), ([0, 2], 1), ([1, 2, 3], 1), ([0, 1, 2], 0),
])
async def test_requires_each_expected_sample(config, tested, expected):
    turn = Turn(config, 7, window=2, fork=3)
    saved_turn(turn)
    for sample in tested:
        saved_test(turn, sample)
    assert await ExperimentDatabase(config.output).query(
        CHECK, **turn.params, samples=3,
    ) == [{'untested': expected}]


@pytest.mark.parametrize('other', [(1, 3, 7), (2, 1, 7), (2, 3, 6)])
async def test_other_windows_forks_and_turns_do_not_supply_tests(config, other):
    turn = Turn(config, 7, window=2, fork=3)
    saved_turn(turn)
    window, fork, position = other
    unrelated = Turn(config, position, window=window, fork=fork)
    saved_turn(unrelated)
    saved_test(unrelated, 0)
    assert await ExperimentDatabase(config.output).query(
        CHECK, **turn.params, samples=1,
    ) == [{'untested': 1}]


async def test_published_tests_update_the_check(config):
    turn = Turn(config, 0)
    saved_turn(turn)
    write(turn.t_dir(0) / 'tests.json.tmp', '{"cases": []}')
    database = ExperimentDatabase(config.output)
    assert await database.query(CHECK, **turn.params, samples=1) == [{'untested': 1}]
    saved_test(turn, 0)
    assert await database.query(CHECK, **turn.params, samples=1) == [{'untested': 0}]


async def test_missing_turn_is_left_to_earlier_checks(config):
    config.output.mkdir()
    assert await ExperimentDatabase(config.output).query(
        CHECK, window=0, fork=0, turn=0, samples=1,
    ) == [{'untested': 1}]
