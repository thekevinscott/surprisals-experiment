"""Every requested sample needs its own completed generation artifact."""

import json
from pathlib import Path

import pytest

from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.utils.write import write

CHECK = Path(__file__).parents[2] / 'src/surprisals_experiment/sdk/run_experiment/states/solutions_missing.sql'


def saved_turn(root, window=2, fork=3, turn=4):
    folder = root / 'windows' / str(window) / 'forks' / str(fork)
    write(folder.parent.parent / 'window.json', '{}')
    write(folder / 'fork.json', '{}')
    write(root / 'advices/example/advice.txt', 'Double it.')
    write(root / 'advices/example/advice.json', '{"score": 0}')
    directory = folder / 'turns' / str(turn)
    write(directory / 'metadata.json', '{"advice": "advices/example"}')
    return directory


@pytest.mark.parametrize('completed,missing', [([], 1), ([0], 1), ([0, 2], 1), ([0, 1], 0)])
async def test_checks_each_sample_position(tmp_path, completed, missing):
    turn = saved_turn(tmp_path)
    for sample in completed:
        write(turn / 'ts' / str(sample) / 'generation.json', '{"exit_code": 0}')
    assert await ExperimentDatabase(tmp_path).query(CHECK, window=2, fork=3, turn=4, samples=2) == [{'solutions_missing': missing}]


@pytest.mark.parametrize('exit_code,missing', [(-1, 1), (0, 0), (1, 0)])
async def test_interrupted_generation_is_not_complete(tmp_path, exit_code, missing):
    turn = saved_turn(tmp_path)
    write(turn / 'ts/0/generation.json', json.dumps({'exit_code': exit_code}))
    assert await ExperimentDatabase(tmp_path).query(CHECK, window=2, fork=3, turn=4, samples=1) == [{'solutions_missing': missing}]


@pytest.mark.parametrize('coordinates', [(0, 3, 4), (2, 0, 4), (2, 3, 0)])
async def test_generations_from_other_turns_do_not_fill_requested_samples(tmp_path, coordinates):
    saved_turn(tmp_path)
    other = saved_turn(tmp_path, *coordinates)
    write(other / 'ts/0/generation.json', '{"exit_code": 0}')
    assert await ExperimentDatabase(tmp_path).query(CHECK, window=2, fork=3, turn=4, samples=1) == [{'solutions_missing': 1}]


async def test_absent_turn_has_no_missing_solutions(tmp_path):
    assert await ExperimentDatabase(tmp_path).query(CHECK, window=2, fork=3, turn=4, samples=1) == [{'solutions_missing': 0}]


async def test_source_and_tests_do_not_replace_generation_completion(tmp_path):
    turn = saved_turn(tmp_path)
    write(turn / 'ts/0/src/main.py', 'print(2)')
    write(turn / 'ts/0/tests.json', '{"cases": []}')
    database = ExperimentDatabase(tmp_path)
    assert await database.query(CHECK, window=2, fork=3, turn=4, samples=1) == [{'solutions_missing': 1}]
    write(turn / 'ts/0/generation.json', '{"exit_code": -1}')
    assert await database.query(CHECK, window=2, fork=3, turn=4, samples=1) == [{'solutions_missing': 1}]
    write(turn / 'ts/0/generation.json', '{"exit_code": 0}')
    assert await database.query(CHECK, window=2, fork=3, turn=4, samples=1) == [{'solutions_missing': 0}]
