from pathlib import Path

import pytest

from surprisals_experiment.sdk.database import ExperimentDatabase

SQL = Path(__file__).parents[2] / 'src/surprisals_experiment/sdk/run_experiment/states/not_started.sql'


@pytest.mark.parametrize(('files', 'expected'), [
    ([], True),
    (['windows/0/window.json'], True),
    (['windows/0/forks/0/fork.json'], True),
    (['windows/0/window.json', 'windows/0/forks/1/fork.json'], True),
    (['windows/0/window.json', 'windows/1/window.json', 'windows/1/forks/0/fork.json'], True),
    (['windows/0/window.json', 'windows/0/forks/0/fork.json'], False),
])
async def test_not_started_checks_the_initial_window_and_fork(tmp_path, files, expected):
    for file in files:
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')

    assert await ExperimentDatabase(tmp_path).query(SQL) == [{'not_started': expected}]
