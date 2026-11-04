"""Feedback state is the presence of the scoped turn's published artifact."""

import json
from pathlib import Path

import pytest

import surprisals_experiment
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.write import write

CHECK = Path(surprisals_experiment.__file__).parent / 'sdk/run_experiment/states/feedback_missing.sql'


def saved_turn(turn):
    write(turn.config.output / f'windows/{turn.window}/window.json', '{}')
    write(turn.attempt_dir.parent.parent / 'fork.json', '{}')
    advice = Advice('double', turn.config.advice_measure, turn.config.output)
    advice.save()
    write(advice.directory / 'advice.json', '{"score": 6}')
    write(turn.attempt_dir / 'metadata.json', json.dumps({
        'advice': str(advice.directory.relative_to(turn.config.output)),
    }))


@pytest.mark.parametrize('content', ['', 'Feedback for the next turn'])
async def test_published_feedback_updates_live_and_reopened_database(config, content):
    turn = Turn(config, 7, window=2, fork=3)
    saved_turn(turn)
    write(turn.attempt_dir / 'feedback.txt.tmp', content)
    database = ExperimentDatabase(config.output)
    assert await database.query(CHECK, **turn.params) == [{'feedback_missing': 1}]
    write(turn.attempt_dir / 'feedback.txt', content)
    assert await database.query(CHECK, **turn.params) == [{'feedback_missing': 0}]
    assert await ExperimentDatabase(config.output).query(CHECK, **turn.params) == [{'feedback_missing': 0}]
    assert await database.query('SELECT * FROM feedback') == [{
        'turn_id': str(turn.attempt_dir.relative_to(config.output)),
    }]


@pytest.mark.parametrize('other', [(1, 3, 7), (2, 1, 7), (2, 3, 6)])
async def test_feedback_in_other_windows_forks_and_turns_does_not_match(config, other):
    turn = Turn(config, 7, window=2, fork=3)
    saved_turn(turn)
    window, fork, position = other
    unrelated = Turn(config, position, window=window, fork=fork)
    saved_turn(unrelated)
    write(unrelated.attempt_dir / 'feedback.txt', 'feedback')
    assert await ExperimentDatabase(config.output).query(CHECK, **turn.params) == [{'feedback_missing': 1}]


async def test_missing_turn_is_left_to_earlier_checks(config):
    config.output.mkdir()
    database = ExperimentDatabase(config.output)
    assert await database.query('SELECT * FROM feedback') == []
    assert await database.query(CHECK, window=0, fork=0, turn=0) == [{'feedback_missing': 1}]
