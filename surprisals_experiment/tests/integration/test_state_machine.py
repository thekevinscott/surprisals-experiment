"""Disk-derived fork rounds and restart behavior."""

import asyncio
import json
from pathlib import Path

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.database import QuestionDatabase
from surprisals_experiment.sdk.run_experiment.run_experiment import state, turn_state
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.write import write

PASS = 'print(int(input()) * 2)\n'


def saved_turn(config, window=0, fork=0, turn=0, *, score=100, passed=True, stage='complete'):
    owned = Turn(config, turn, window, fork)
    write(config.output / 'windows' / str(window) / 'window.json', '{}')
    write(owned.attempt_dir.parent.parent / 'fork.json', '{}')
    if stage == 'advice_missing':
        return owned
    advice = Advice(f'{window}/{fork}/{turn}: {score}', config.advice_measure, config.output)
    advice.save()
    write(owned.attempt_dir / 'metadata.json', json.dumps({'advice': str(advice.directory.relative_to(config.output))}))
    if stage == 'unscored':
        return owned
    write(advice.directory / 'advice.json', json.dumps({'score': score}))
    if stage == 'solutions_missing':
        return owned
    for sample in range(config.t_samples):
        folder = owned.t_dir(sample)
        write(folder / 'src/main.py', PASS)
        write(folder / 'run.json', '{"exit_code":0}')
        if stage != 'untested':
            write(folder / 'tests.json', json.dumps({'cases': [dict(index=0, passed=passed, status='passed' if passed else 'wrong_answer', stdout='', stderr='')]}))
    if stage == 'complete':
        write(owned.attempt_dir / 'feedback.txt', 'feedback')
    return owned


def saved_window(config, window, *, score=100, winner=0, passed=True):
    for fork in range(4):
        for turn in range(10):
            saved_turn(config, window, fork, turn, score=score if fork == winner else score + 10, passed=passed)
    for turn in range(10, 40):
        saved_turn(config, window, winner if passed else 0, turn, score=score, passed=passed)


@pytest.mark.parametrize('stage', ['advice_missing', 'unscored', 'solutions_missing', 'untested', 'feedback_missing', 'complete'])
async def test_folder_classifies_each_turn_stage(config, stage):
    owned = saved_turn(config, stage=stage)
    database = ExperimentDatabase(config.output)
    assert (await turn_state(owned, database))['state'] == stage
    assert (await state(config, database))['state'] == 'fork_round'


@pytest.mark.parametrize('winner,passed', [(3, True), (0, True), (0, False)])
async def test_round_winner_and_no_pass_default(config, winner, passed):
    config.max_u_turns = 40
    for fork in range(4):
        for turn in range(10):
            saved_turn(config, fork=fork, turn=turn, score=10 if fork == winner else 20, passed=passed)
    assert await state(config, ExperimentDatabase(config.output)) == dict(state='solo', window=0, fork=winner)


async def test_tie_uses_lowest_fork_position(config):
    config.max_u_turns = 40
    for fork in range(4):
        for turn in range(10):
            saved_turn(config, fork=fork, turn=turn, score=10)
    assert (await state(config, ExperimentDatabase(config.output)))['fork'] == 0


async def test_window_rollover_and_partial_turn(config):
    config.max_u_turns = 80
    saved_window(config, 0)
    database = ExperimentDatabase(config.output)
    assert (await state(config, database))['state'] == 'window_missing'
    owned = saved_turn(config, 1, 0, 0, stage='untested')
    assert (await state(config, database))['state'] == 'fork_round'
    assert (await turn_state(owned, database))['state'] == 'untested'


async def test_fork_best_is_isolated_until_solo(config):
    from surprisals_experiment.sdk.run_experiment.prepare_flush.prepare_flush import prepare_flush
    query_file = Path(__file__).parents[2] / 'src/surprisals_experiment/sdk/run_experiment/prepare_flush/fork_best.sql'
    saved_window(config, 0, score=100)
    saved_turn(config, 1, 0, 0, score=20)
    saved_turn(config, 1, 1, 0, score=80)
    problem = QuestionDatabase(config.problem_dir)
    database = ExperimentDatabase(config.output)
    own = await prepare_flush(config, problem, database, query_file=query_file, window=1, fork=1, cutoff=1)
    solo = await prepare_flush(config, problem, database, query_file=query_file, window=1, fork=1, cutoff=11)
    assert '1/1/0: 80' in own
    assert '1/0/0: 20' not in own
    assert '1/0/0: 20' in solo


@pytest.mark.parametrize('seed', [False, True])
async def test_parallel_forks_and_restart_mid_round(config, botbox_script, chat_provider, monkeypatch, seed):
    from conftest import FakeSession
    config.max_u_turns = 1
    original = saved_turn(config, fork=0, turn=0).attempt_dir / 'metadata.json' if seed else None
    before = original.stat().st_mtime_ns if original else None
    expected = 3 if seed else 4
    botbox_script.advice.extend(['double it'] * expected)
    botbox_script.solutions.extend([PASS] * expected)
    entered = set()
    barrier = asyncio.Event()
    reply = FakeSession.message

    async def concurrent(self, text):
        entered.add(str(self.output))
        if len(entered) == expected:
            barrier.set()
        await asyncio.wait_for(barrier.wait(), 5)
        await reply(self, text)

    monkeypatch.setattr(FakeSession, 'message', concurrent)
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == len(botbox_script.sessions) == expected
    if original:
        assert original.stat().st_mtime_ns == before
    assert json.loads(config.result_file.read_text())['attempts'] == 1
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == expected
