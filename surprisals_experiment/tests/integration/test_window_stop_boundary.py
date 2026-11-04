"""The window rule acts only after every turn of the window is complete."""

import asyncio
import importlib
import json

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.run_experiment.run_experiment import state
from surprisals_experiment.sdk.turn import Turn
from test_window_stop import save_turn


def save_window(config, window, score, *, last=39):
    for fork in range(4):
        for position in range(10):
            save_turn(Turn(config, position, window=window, fork=fork), score)
    for position in range(10, last + 1):
        save_turn(Turn(config, position, window=window), score)


@pytest.mark.parametrize('score,stopped', [(96, True), (95, False), (94, False)])
async def test_completed_window_boundary(config, score, stopped):
    config.max_u_turns = None
    save_window(config, 0, 100)
    database = ExperimentDatabase(config.output)
    assert (await state(config, database))['state'] != 'stopped'
    save_window(config, 1, score)
    assert ((await state(config, database))['state'] == 'stopped') is stopped


@pytest.mark.parametrize('cap', [5, 45])
async def test_hard_cap_counts_parallel_turns_once_and_finishes_partial_round(config, cap):
    config.max_u_turns = cap
    window = cap // 40
    if window:
        save_window(config, 0, 100)
    for fork in range(4):
        for position in range(5):
            save_turn(Turn(config, position, window=window, fork=fork), 90)
    last = Turn(config, 4, window=window, fork=3)
    feedback = last.attempt_dir / 'feedback.txt'
    unpublished = last.attempt_dir / '.unpublished-feedback'
    feedback.rename(unpublished)
    database = ExperimentDatabase(config.output)
    assert (await state(config, database))['state'] != 'stopped'
    unpublished.rename(feedback)
    assert (await state(config, database))['state'] == 'stopped'


@pytest.mark.parametrize('interrupt', [False, True])
async def test_finish_last_turn_then_stop_and_restart_without_repeated_calls(
    config, botbox_script, chat_provider, monkeypatch, interrupt,
):
    config.max_u_turns = None
    save_window(config, 0, 100)
    save_window(config, 1, 96, last=38)
    assert (await state(config, ExperimentDatabase(config.output)))['state'] != 'stopped'
    botbox_script.advice.append('x' * 96)
    botbox_script.solutions.append('print(int(input()) * 2)\n')
    module = importlib.import_module('surprisals_experiment.sdk.run_test_suite.run_test_suite')
    original = module.run_test_suite_for_t

    if interrupt:
        async def cancel(suite, solution):
            raise asyncio.CancelledError

        monkeypatch.setattr(module, 'run_test_suite_for_t', cancel)
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
        assert (await state(config, ExperimentDatabase(config.output)))['state'] != 'stopped'
        monkeypatch.setattr(module, 'run_test_suite_for_t', original)

    solution = await run_experiment(config, on_delta=None)
    assert solution == Turn(config, 0, window=1).t_dir(0) / 'src'
    assert json.loads(config.result_file.read_text())['attempts'] == 80
    assert not (config.output / 'windows/2').exists()
    assert len(chat_provider) == len(botbox_script.sessions) == 1
    assert await run_experiment(config, on_delta=None) == solution
    assert len(chat_provider) == len(botbox_script.sessions) == 1
