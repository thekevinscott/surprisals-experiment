from pathlib import Path

import pytest

from surprisals_experiment.sdk.database import ExperimentDatabase

SQL = Path(__file__).parents[2] / 'src/surprisals_experiment/sdk/run_experiment/states/advice_missing.sql'


@pytest.mark.parametrize(('stage', 'requested', 'expected'), [
    (0, (2, 3, 4), True),
    (1, (2, 3, 4), True),
    (2, (2, 3, 4), True),
    (3, (2, 3, 4), True),
    (4, (2, 3, 4), False),
    (4, (2, 3, 5), True),
    (4, (2, 4, 4), True),
    (4, (3, 3, 4), True),
])
async def test_advice_missing_checks_the_requested_turn(tmp_path, stage, requested, expected):
    window = tmp_path / 'windows/2'
    fork = window / 'forks/3'
    turn = fork / 'turns/4'
    if stage >= 1:
        window.mkdir(parents=True)
        (window / 'window.json').write_text('{}')
    if stage >= 2:
        fork.mkdir(parents=True)
        (fork / 'fork.json').write_text('{}')
    if stage >= 3:
        turn.mkdir(parents=True)
    if stage >= 4:
        advice = tmp_path / 'advices/seed'
        advice.mkdir(parents=True)
        (advice / 'advice.txt').write_text('Double it.')
        (advice / 'advice.json').write_text('{"score": 10}')
        (turn / 'metadata.json').write_text('{"advice": "advices/seed"}')

    window, fork, turn = requested
    assert await ExperimentDatabase(tmp_path).query(SQL, window=window, fork=fork, turn=turn) == [
        {'advice_missing': expected},
    ]
