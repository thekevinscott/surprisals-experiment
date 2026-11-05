"""Window stopping and restart use persisted successful scores across the whole run."""

import asyncio
import json
from unittest.mock import patch

import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.run_experiment.run_experiment import actions


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
@pytest.mark.parametrize('scores,passed,windows,best', [
    ([100, 96], [True, True], 2, 1),
    ([100, 95, 95], [True, True, True], 3, 1),
    ([100, 90, 90], [True, True, True], 3, 1),
    ([100, 100], [True, True], 2, 0),
    ([100, 110], [True, True], 2, 0),
    ([100, 90, 96], [True, True, True], 3, 1),
    ([100, 1], [True, False], 2, 0),
    ([100, 90, 90], [False, True, True], 3, 1),
    ([100, 90], [False, False], 2, None),
], ids=['under-five', 'exactly-five', 'over-five', 'equal', 'worse',
        'cumulative-best', 'failed-lower-score', 'first-success-later', 'no-success'])
async def test_window_stop(config, botbox_script, chat_provider, scorer_provider,
                           measure, scores, passed, windows, best):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1', 't_samples': 2,
    }))
    for score, success in zip(scores, passed):
        advice = 'x' * score if measure == 'characters' else f'score {score}'
        botbox_script.advice.append(advice)
        scorer_provider.replies.append([(advice, score / 10)])
        botbox_script.solutions.extend(['print(int(input()) * 2)',
                                       'print(int(input()) * 2)' if success else 'print(0)'])
    solution = await run_experiment(config, on_delta=None)
    expected = config.output / f'windows/{best}/forks/0/turns/0/ts/0/src' if best is not None else None
    assert solution == expected
    database = ExperimentDatabase(config.output)
    assert await database.query('SELECT position FROM windows ORDER BY position') == [
        {'position': position} for position in range(windows)
    ]
    assert len(chat_provider) == windows
    assert len(botbox_script.sessions) == windows * 2
    result = json.loads(config.result_file.read_text())
    assert result['attempts'] == windows
    assert result['success'] == (best is not None)
    assert result['solution'] == (str(expected) if expected else None)
    with patch('surprisals_experiment.sdk.utils.u_chat.ChatSession.prompt',
               side_effect=AssertionError('Completed run asked U again')):
        assert await run_experiment(config, on_delta=None) == solution


async def test_window_zero_always_continues_and_restart_does_not_repeat_work(config, botbox_script, chat_provider):
    botbox_script.advice.extend(['Double it.', 'Double it.'])
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 2)
    advance = actions['window_pending']
    calls = 0

    async def interrupt_between_windows(run):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise asyncio.CancelledError
        await advance(run)

    with patch.dict(actions, {'window_pending': interrupt_between_windows}):
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
    generation = config.t_dir(0, 0) / 'generation.json'
    before = (generation.read_bytes(), generation.stat().st_mtime_ns)
    assert len(chat_provider) == 1
    assert not (config.output / 'windows/1').exists()

    solution = await run_experiment(config, on_delta=None)
    assert solution == config.t_dir(0, 0) / 'src'
    assert len(chat_provider) == 2
    assert len(botbox_script.sessions) == 2
    assert (generation.read_bytes(), generation.stat().st_mtime_ns) == before
    assert json.loads(config.result_file.read_text())['attempts'] == 2


async def test_incomplete_second_window_resumes_before_comparing(config, botbox_script, chat_provider):
    botbox_script.advice.extend(['Double it.', 'Double it.'])
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 2)
    produce = actions['solutions_missing']

    async def interrupt(run, turn):
        if turn.window == 1:
            raise asyncio.CancelledError
        await produce(run, turn)

    with patch.dict(actions, {'solutions_missing': interrupt}):
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
    generation = config.t_dir(0, 0) / 'generation.json'
    before = (generation.read_bytes(), generation.stat().st_mtime_ns)
    assert len(chat_provider) == 2
    assert len(botbox_script.sessions) == 1
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(chat_provider) == 2
    assert len(botbox_script.sessions) == 2
    assert (generation.read_bytes(), generation.stat().st_mtime_ns) == before
    assert json.loads(config.result_file.read_text())['attempts'] == 2


async def test_zero_best_score_stops_after_two_windows(config, botbox_script, scorer_provider):
    config = Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
    }))
    botbox_script.advice.extend(['zero'] * 2)
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 2)
    scorer_provider.replies.append([('zero', 0.0)])
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert json.loads(config.result_file.read_text())['attempts'] == 2
    assert len(scorer_provider.requests) == 1
