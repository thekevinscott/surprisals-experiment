"""Window comparisons use only completed, all-pass advice from disk."""

import json

import pytest

from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.write import write
from surprisals_experiment.sdk.run_experiment.run_experiment import QUERIES


def save_turn(turn, score, *, passed=True, complete=True):
    write(turn.config.output / f'windows/{turn.window}/window.json', '{}')
    write(turn.attempt_dir.parent.parent / 'fork.json', '{}')
    advice = Advice(f'{turn.params}: {score}', turn.config.advice_measure, turn.config.output)
    advice.save()
    write(advice.directory / 'advice.json', json.dumps({'score': score}))
    write(turn.attempt_dir / 'metadata.json', json.dumps({
        'advice': str(advice.directory.relative_to(turn.config.output)),
    }))
    for sample in range(turn.config.t_samples):
        write(turn.t_dir(sample) / 'src/main.py', 'print(int(input()) * 2)\n')
        write(turn.t_dir(sample) / 'run.json', '{"exit_code": 0}')
        write(turn.t_dir(sample) / 'tests.json', json.dumps({'cases': [{
            'index': 0, 'passed': passed, 'status': 'passed' if passed else 'wrong_answer',
            'stdout': '', 'stderr': '',
        }]}))
    if complete:
        write(turn.attempt_dir / 'feedback.txt', 'feedback')


@pytest.mark.parametrize('previous,current,stopped', [
    (100, 96, True), (100, 95, False), (100, 94, False),
    (100, 100, True), (100, 101, True), (0, 0, True),
    (None, None, True), (None, 100, False), (100, None, True),
    (7.5, 7.125, False), (7.5, 7.126, True),
])
async def test_five_percent_threshold(config, previous, current, stopped):
    for window, score in enumerate((previous, current)):
        save_turn(Turn(config, 0, window=window), score or 0, passed=score is not None)
    result, = await ExperimentDatabase(config.output).query(
        QUERIES / 'window_stop.sql', window=1, samples=config.t_samples,
    )
    assert bool(result['stopped']) is stopped


@pytest.mark.parametrize('passed', [True, False])
async def test_first_window_never_stops(config, passed):
    save_turn(Turn(config, 0), 0, passed=passed)
    result, = await ExperimentDatabase(config.output).query(
        QUERIES / 'window_stop.sql', window=0, samples=config.t_samples,
    )
    assert not result['stopped']


async def test_cumulative_best_ignores_failed_partial_and_future_turns(config):
    save_turn(Turn(config, 0), 100)
    save_turn(Turn(config, 0, window=1), 120)
    save_turn(Turn(config, 0, window=2, fork=3), 96)
    save_turn(Turn(config, 1, window=2), 90, passed=False)
    save_turn(Turn(config, 2, window=2), 80, complete=False)
    save_turn(Turn(config, 0, window=3), 70)
    result, = await ExperimentDatabase(config.output).query(
        QUERIES / 'window_stop.sql', window=2, samples=config.t_samples,
    )
    assert result['stopped'] == 1


async def test_missing_sample_does_not_improve_best(config):
    config.t_samples = 2
    save_turn(Turn(config, 0), 100)
    save_turn(Turn(config, 0, window=1), 96)
    partial = Turn(config, 1, window=1)
    save_turn(partial, 50)
    (partial.t_dir(1) / 'tests.json').rename(partial.t_dir(1) / '.unpublished-tests')
    result, = await ExperimentDatabase(config.output).query(
        QUERIES / 'window_stop.sql', window=1, samples=config.t_samples,
    )
    assert result['stopped'] == 1
