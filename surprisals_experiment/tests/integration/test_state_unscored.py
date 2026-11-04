"""The unscored check reads the requested turn's persisted score."""

import json
from pathlib import Path

import pytest

from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.utils.write import write

CHECK = Path(__file__).parents[2] / 'src/surprisals_experiment/sdk/run_experiment/states/unscored.sql'


def advice(root, window=2, fork=3, turn=4):
    folder = root / 'windows' / str(window) / 'forks' / str(fork)
    write(folder.parent.parent / 'window.json', '{}')
    write(folder / 'fork.json', '{}')
    write(root / 'advices/example/advice.txt', 'Double it.')
    write(folder / 'turns' / str(turn) / 'metadata.json', '{"advice": "advices/example"}')


@pytest.mark.parametrize('score', [None, 0, 12.5])
async def test_unscored_until_score_is_published(tmp_path, score):
    advice(tmp_path)
    if score is not None:
        write(tmp_path / 'advices/example/advice.json', json.dumps({'score': score}))
    database = ExperimentDatabase(tmp_path)
    assert await database.query(CHECK, window=2, fork=3, turn=4) == [{'unscored': int(score is None)}]


@pytest.mark.parametrize('coordinates', [(0, 3, 4), (2, 0, 4), (2, 3, 0)])
async def test_other_turns_do_not_make_requested_turn_unscored(tmp_path, coordinates):
    advice(tmp_path)
    window, fork, turn = coordinates
    assert await ExperimentDatabase(tmp_path).query(CHECK, window=window, fork=fork, turn=turn) == [{'unscored': 0}]


async def test_empty_run_is_not_unscored(tmp_path):
    assert await ExperimentDatabase(tmp_path).query(CHECK, window=0, fork=0, turn=0) == [{'unscored': 0}]


async def test_check_observes_score_published_after_first_query(tmp_path):
    advice(tmp_path)
    database = ExperimentDatabase(tmp_path)
    assert await database.query(CHECK, window=2, fork=3, turn=4) == [{'unscored': 1}]
    write(tmp_path / 'advices/example/advice.json', '{"score": 0}')
    assert await database.query(CHECK, window=2, fork=3, turn=4) == [{'unscored': 0}]
