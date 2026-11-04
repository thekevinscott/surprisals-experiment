"""Folder-derived sequential state, stopping budgets, and real process restart."""

import json

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.run_experiment.run_experiment import state, turn_state
from surprisals_experiment.sdk.utils.write import write

PASS = 'print(int(input()) * 2)\n'


def saved_turn(config, turn=0, *, score=100, passed=True, stage='complete'):
    write(config.window_dir / 'window.json', '{}')
    write(config.fork_dir / 'fork.json', '{}')
    if stage == 'advice_missing':
        return
    advice = Advice(f'{turn}: {score}', config.advice_measure, config.output)
    advice.save()
    write(config.attempt_dir(turn) / 'metadata.json', json.dumps({'advice': str(advice.directory.relative_to(config.output))}))
    if stage == 'unscored':
        return
    write(advice.directory / 'advice.json', json.dumps({'score': score}))
    if stage == 'solutions_missing':
        return
    for sample in range(config.t_samples):
        folder = config.t_dir(turn, sample)
        write(folder / 'src/main.py', PASS)
        write(folder / 'run.json', '{"exit_code":0}')
        if stage != 'untested':
            write(folder / 'tests.json', json.dumps({'cases': [dict(index=0, passed=passed, status='passed' if passed else 'wrong_answer', stdout='', stderr='')]}))
    if stage == 'complete':
        write(config.attempt_dir(turn) / 'feedback.txt', 'feedback')


@pytest.mark.parametrize('stage', ['advice_missing', 'unscored', 'solutions_missing', 'untested', 'feedback_missing', 'complete'])
async def test_folder_classifies_each_turn_stage(config, stage):
    saved_turn(config, stage=stage)
    database = ExperimentDatabase(config.output)
    assert (await turn_state(Turn(config, 0), database))['state'] == stage
    actual = await state(config, database)
    assert actual == dict(state='stopped' if stage == 'complete' else 'turn', turn=1 if stage == 'complete' else 0)


@pytest.mark.parametrize('scores,passed,expected', [
    ([10,10], [False,False], 'stopped'),
    ([10,10], [False,True], 'turn'),
    ([10,10,11], [True,True,True], 'stopped'),
    ([10,9,8], [True,False,False], 'stopped'),
    ([10,10,9], [True,False,True], 'turn'),
])
async def test_stale_budget_counts_only_strict_passing_improvements(config, scores, passed, expected):
    config.max_u_turns = None
    config.max_turns_without_improvement = 2
    for turn, (score, success) in enumerate(zip(scores, passed)):
        saved_turn(config, turn, score=score, passed=success)
    assert await state(config, ExperimentDatabase(config.output)) == dict(state=expected, turn=len(scores))


async def test_partial_turn_is_finished_before_stopping(config):
    config.max_u_turns = 2
    config.max_turns_without_improvement = 1
    saved_turn(config, 0, passed=False)
    saved_turn(config, 1, stage='untested')
    assert await state(config, ExperimentDatabase(config.output)) == dict(state='turn', turn=1)


async def test_no_forty_turn_limit_or_window_rollover(config):
    config.max_u_turns = 42
    config.max_turns_without_improvement = 100
    for turn in range(41):
        saved_turn(config, turn)
    assert await state(config, ExperimentDatabase(config.output)) == dict(state='turn', turn=41)
    saved_turn(config, 41)
    assert await state(config, ExperimentDatabase(config.output)) == dict(state='stopped', turn=42)
    assert [p.name for p in (config.output/'windows').iterdir()] == ['0']
    assert [p.name for p in (config.window_dir/'forks').iterdir()] == ['0']


async def test_completed_run_restart_makes_no_calls(config, botbox_script, chat_provider):
    botbox_script.advice.append('double')
    botbox_script.solutions.append(PASS)
    first = await run_experiment(config, on_delta=None)
    assert await run_experiment(config, on_delta=None) == first
    assert len(chat_provider) == len(botbox_script.sessions) == 1


async def test_missing_generation_file_prevents_completed_turn(config):
    saved_turn(config)
    (config.t_dir(0,0) / 'run.json').rename(config.t_dir(0,0) / '.unpublished-run')
    database = ExperimentDatabase(config.output)
    assert (await turn_state(Turn(config, 0), database))['state'] == 'solutions_missing'
    assert (await state(config, database))['state'] == 'turn'


async def test_restart_warns_on_commit_change_without_rewriting_settings(config):
    config.save_settings()
    path = config.output / 'settings.json'
    data = json.loads(path.read_text())
    data['git_commit'] = 'old-commit'
    write(path, json.dumps(data))
    with pytest.warns(UserWarning, match='different git commit'):
        config.save_settings()
    assert json.loads(path.read_text())['git_commit'] == 'old-commit'


def test_process_exit_mid_ts_resumes_without_repeated_calls(config, tmp_path):
    """Kill the interpreter after two published Ts; resume in a new interpreter."""
    import subprocess
    import sys
    worker = tmp_path / 'worker.py'
    worker.write_text(r'''
import asyncio
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.advice_measure import AdviceMeasure
from surprisals_experiment.sdk.utils.u_chat.chat_session import ChatSession
from surprisals_experiment.sdk.utils.write import write

root = Path(sys.argv[1])
config = Config(api_key='unused', problem_dir=root/'problem', output=root/'run',
                u_model='fake', t_model='fake', u_thinking='off', t_samples=5,
                t_pool_size=1, max_u_turns=1)

def record_call(path):
    count = int(path.read_text()) if path.exists() else 0
    write(path, str(count+1))

async def reply(self, *, on_delta=None):
    record_call(root/'calls/U'/self.transcript.relative_to(config.output))
    self.record({'role':'assistant', 'content':'double'}, complete=True)
    return 'double'

async def score(self, text, *, on_delta=None):
    record_call(root/'calls/score')
    return 6, None

async def prompt_t(config, advice, *, output, logs, on_delta=None):
    if sys.argv[2] == 'crash' and len(list(config.output.glob('windows/*/forks/*/turns/*/ts/*/run.json'))) >= 2:
        os._exit(17)
    record_call(root/'calls/T'/logs.relative_to(config.output)/'count')
    write(output/'main.py', 'print(int(input()) * 2)\n')
    return SimpleNamespace(exit_code=0)

ChatSession.reply = reply
AdviceMeasure.score = score
importlib.import_module('surprisals_experiment.sdk.run_experiment.actions.write_solutions.produce_code').prompt_t = prompt_t
asyncio.run(run_experiment(config, on_delta=None))
''')
    interrupted = subprocess.run([sys.executable, str(worker), str(tmp_path), 'crash'], capture_output=True, text=True, timeout=15)
    assert interrupted.returncode == 17, interrupted.stderr
    assert len(list(config.output.glob('windows/*/forks/*/turns/*/ts/*/run.json'))) == 2
    resumed = subprocess.run([sys.executable, str(worker), str(tmp_path), 'resume'], capture_output=True, text=True, timeout=15)
    assert resumed.returncode == 0, resumed.stderr
    u_calls = list((tmp_path/'calls/U').rglob('messages.jsonl'))
    t_calls = list((tmp_path/'calls/T').rglob('count'))
    assert len(u_calls) == 1 and len(t_calls) == 5
    assert all(path.read_text() == '1' for path in [*u_calls, *t_calls, tmp_path/'calls/score'])


async def test_restart_keeps_completed_test_results(config, botbox_script, chat_provider, monkeypatch):
    import asyncio
    import importlib
    from collections import Counter

    config.t_samples = 3
    botbox_script.advice.append('double')
    botbox_script.solutions.extend([PASS] * 3)
    module = importlib.import_module('surprisals_experiment.sdk.run_test_suite.run_test_suite')
    original = module.run_test_suite_for_t
    calls = Counter()
    interrupted = False

    async def evaluate(suite, solution):
        nonlocal interrupted
        calls[solution] += 1
        if solution == config.t_dir(0,1) / 'src' and not interrupted:
            interrupted = True
            raise asyncio.CancelledError
        return await original(suite, solution)

    monkeypatch.setattr(module, 'run_test_suite_for_t', evaluate)
    with pytest.raises(asyncio.CancelledError):
        await run_experiment(config, on_delta=None)
    completed = config.t_dir(0,0) / 'tests.json'
    before = completed.stat().st_mtime_ns
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 1
    assert len(botbox_script.sessions) == 3
    assert calls[config.t_dir(0,0) / 'src'] == 1
    assert calls[config.t_dir(0,1) / 'src'] == 2
    assert calls[config.t_dir(0,2) / 'src'] == 1
    assert completed.stat().st_mtime_ns == before

async def test_restart_uses_saved_settings_over_changed_config(config, botbox_script, chat_provider):
    config.t_samples = 2
    config.max_u_turns = 1
    config.save_settings()
    saved_turn(config, stage='solutions_missing')
    settings = config.output / 'settings.json'
    before = settings.read_bytes()
    changed = config.model_copy(update={
        't_samples': 1, 'max_u_turns': 3,
        'problem_dir': config.output / 'not-the-original-problem',
    })
    botbox_script.solutions.extend([PASS] * 2)
    assert await run_experiment(changed, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(botbox_script.sessions) == 2
    assert not chat_provider
    assert (config.t_dir(0, 1) / 'tests.json').exists()
    assert not config.attempt_dir(1).exists()
    assert settings.read_bytes() == before
