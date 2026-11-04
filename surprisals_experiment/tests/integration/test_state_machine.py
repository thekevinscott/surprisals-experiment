"""Real folder -> classifier, parallel fork rounds, and interruption/restart."""

import asyncio
import json
from collections import Counter
from pathlib import Path

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.database import ExperimentDatabase
from surprisals_experiment.sdk.run_experiment.run_experiment import state, fork_state
from surprisals_experiment.sdk.run_experiment.queries import query
from surprisals_experiment.sdk.utils.write import write

PASS = 'print(int(input()) * 2)\n'
QUERIES = Path(__import__('surprisals_experiment').__file__).parent / 'sdk/run_experiment/queries'


async def saved_turn(config, window=0, fork=0, turn=0, *, score=100, passed=True, stage='complete'):
    scoped = config.at(window=window, fork=fork, turn=turn)
    write(scoped.window_dir / 'window.json', '{}')
    write(scoped.fork_dir / 'fork.json', '{}')
    if stage == 'advice_missing':
        return scoped
    advice = Advice(f'{window}/{fork}/{turn}: {score}', config.advice_measure, config.output)
    advice.save()
    write(scoped.attempt_dir(turn) / 'metadata.json', json.dumps({'advice': str(advice.directory.relative_to(config.output))}))
    if stage == 'unscored':
        return scoped
    write(advice.directory / 'advice.json', json.dumps({'score': score}))
    if stage == 'solutions_missing':
        return scoped
    for sample in range(config.t_samples):
        folder = scoped.t_dir(turn, sample)
        write(folder / 'src/main.py', PASS)
        write(folder / 'run.json', '{"exit_code":0}')
        if stage != 'untested':
            write(folder / 'tests.json', json.dumps({'cases': [dict(index=0, passed=passed, status='passed' if passed else 'wrong_answer', stdout='', stderr='')]}))
    if stage == 'complete':
        write(scoped.attempt_dir(turn) / 'feedback.txt', 'feedback')
    return scoped


async def saved_window(config, window, *, score=100, winner=0, passed=True):
    for fork in range(4):
        for turn in range(10):
            await saved_turn(config, window, fork, turn, score=score if fork == winner else score+10, passed=passed)
    for turn in range(10,40):
        await saved_turn(config, window, winner if passed else 0, turn, score=score, passed=passed)


@pytest.mark.parametrize('stage', ['advice_missing', 'unscored', 'solutions_missing', 'untested', 'feedback_missing', 'complete'])
async def test_folder_classifies_each_turn_stage(config, stage):
    await saved_turn(config, stage=stage)
    actual = await fork_state(config, ExperimentDatabase(config.output))
    assert actual['state'] == stage
    assert (await state(config, ExperimentDatabase(config.output)))['state'] == 'fork_round'


@pytest.mark.parametrize('winner,passed', [(3, True), (0, True), (0, False)])
async def test_round_winner_and_no_pass_default(config, winner, passed):
    config.max_u_turns = 40
    for fork in range(4):
        for turn in range(10):
            await saved_turn(config, fork=fork, turn=turn, score=10 if fork == winner else 20, passed=passed)
    result = await state(config, ExperimentDatabase(config.output))
    assert result == dict(state='solo', window=0, fork=winner)


async def test_round_ties_choose_lowest_fork_position(config):
    config.max_u_turns = 40
    for fork in range(4):
        for turn in range(10):
            await saved_turn(config, fork=fork, turn=turn, score=10)
    assert (await state(config, ExperimentDatabase(config.output)))['fork'] == 0


@pytest.mark.parametrize('score,expected', [(96, 'stopped'), (95, 'window_missing'), (94, 'window_missing')])
async def test_stop_rule_compares_finished_windows(config, score, expected):
    config.max_u_turns = None
    await saved_window(config, 0)
    database = ExperimentDatabase(config.output)
    assert (await state(config, database))['state'] == 'window_missing'
    await saved_window(config, 1, score=score)
    assert (await state(config, database))['state'] == expected


async def test_no_pass_windows_stop_after_window_one(config):
    config.max_u_turns = None
    await saved_window(config, 0, passed=False)
    assert (await state(config, ExperimentDatabase(config.output)))['state'] == 'window_missing'
    await saved_window(config, 1, passed=False)
    assert (await state(config, ExperimentDatabase(config.output)))['state'] == 'stopped'


async def test_incomplete_turn_cannot_trigger_cap_or_stop(config):
    config.max_u_turns = 80
    await saved_window(config, 0)
    await saved_window(config, 1)
    last = config.at(window=1).attempt_dir(39) / 'feedback.txt'
    # Simulate a crash immediately before feedback publication.
    last.rename(last.with_name('.unpublished-feedback'))
    assert (await state(config, ExperimentDatabase(config.output)))['state'] == 'solo'


async def test_prompt_numbers_and_fork_isolation(config):
    config.max_u_turns = None
    await saved_window(config, 0, score=100)
    await saved_turn(config, 1, 0, 0, score=20)
    await saved_turn(config, 1, 1, 0, score=80)
    scoped = config.at(window=1, fork=1, turn=1)
    database = ExperimentDatabase(config.output)
    numbers, = await query(database, scoped, QUERIES.parents[1] / 'utils/u_chat/prompt_numbers.sql')
    assert numbers == dict(window=1, turn=2, turns=40, start_best=100, target=95)
    from surprisals_experiment.sdk.run_experiment.prepare_flush.prepare_flush import BEST_ATTEMPT
    best, = await query(database, scoped, BEST_ATTEMPT)
    assert best['score'] == 80
    solo = config.at(window=1, fork=1, turn=10)
    best, = await query(database, solo, BEST_ATTEMPT)
    assert best['score'] == 20


async def test_parallel_forks_and_time_cap(config, botbox_script, chat_provider, monkeypatch):
    from conftest import FakeSession
    config.max_u_turns = 1
    botbox_script.advice.extend(['double it'] * 4)
    botbox_script.solutions.extend([PASS] * 4)
    entered = set()
    barrier = asyncio.Event()
    original = FakeSession.message

    async def message(self, text):
        entered.add(str(self.output))
        if len(entered) == 4:
            barrier.set()
        await asyncio.wait_for(barrier.wait(), 5)
        await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', message)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0,0) / 'src'
    assert len(chat_provider) == len(botbox_script.sessions) == 4
    assert json.loads(config.result_file.read_text())['attempts'] == 1
    assert all('turn 1 of 40' in request['messages'][0]['content'] for request in chat_provider)
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == len(botbox_script.sessions) == 4


async def test_restart_mid_batch_keeps_finished_u_t_and_scores(config, botbox_script, chat_provider, monkeypatch):
    from conftest import FakeSession
    config.t_samples = 3
    config.t_pool_size = 1
    botbox_script.advice.extend(['double it'] * 4)
    botbox_script.solutions.extend([PASS] * 12)
    original = FakeSession.message
    calls = Counter()
    reached = asyncio.Event()

    async def interrupt(self, text):
        if len(list(config.output.glob('windows/*/forks/*/turns/*/ts/*/run.json'))) >= 4:
            reached.set()
            await asyncio.Event().wait()
        calls[str(self.output)] += 1
        await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', interrupt)
    task = asyncio.create_task(run_experiment(config, on_delta=None))
    await asyncio.wait_for(reached.wait(), 10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    finished = {str(path.parent) for path in config.output.glob('windows/*/forks/*/turns/*/ts/*/run.json')}
    assert 0 < len(finished) < 12
    before = dict(calls)
    scores = {path: path.stat().st_mtime_ns for path in config.output.glob('advices/*/advice.json')}

    async def resume(self, text):
        calls[str(self.output)] += 1
        await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', resume)
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 4
    assert all(calls[path] == before[path] == 1 for path in finished)
    assert sum(calls.values()) == 12
    assert all(path.stat().st_mtime_ns == mtime for path, mtime in scores.items())
    assert (await state(config, ExperimentDatabase(config.output)))['state'] == 'stopped'


async def test_restart_warns_on_commit_change_without_rewriting_settings(config):
    config.save_settings()
    path = config.output / 'settings.json'
    data = json.loads(path.read_text())
    data['git_commit'] = 'old-commit'
    write(path, json.dumps(data))
    with pytest.warns(UserWarning, match='different git commit'):
        config.save_settings()
    assert json.loads(path.read_text())['git_commit'] == 'old-commit'


@pytest.mark.parametrize('passed,winner', [(True, 3), (False, 0)])
async def test_resume_round_runs_only_winner_solo(config, botbox_script, chat_provider, passed, winner):
    config.max_u_turns = 11
    for fork in range(4):
        for turn in range(10):
            await saved_turn(config, fork=fork, turn=turn, score=10 if fork == winner else 20, passed=passed)
    original = {path: path.read_bytes() for path in config.output.glob('windows/0/forks/*/turns/*/metadata.json')}
    botbox_script.advice.append('x')
    botbox_script.solutions.append(PASS)
    result = await run_experiment(config, on_delta=None)
    assert result == config.at(window=0, fork=winner).t_dir(10,0) / 'src'
    assert len(chat_provider) == len(botbox_script.sessions) == 1
    assert all(path.read_bytes() == content for path, content in original.items())
    assert len(list(config.output.glob('windows/0/forks/*/turns/10'))) == 1
    assert json.loads(config.result_file.read_text())['attempts'] == 11


async def test_restart_opens_next_window_with_window_start_best(config, botbox_script, chat_provider):
    config.max_u_turns = 41
    await saved_window(config, 0, score=100)
    botbox_script.advice.extend(['short'] * 4)
    botbox_script.solutions.extend([PASS] * 4)
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == len(botbox_script.sessions) == 4
    assert all('Window 1, turn 1 of 40' in request['messages'][0]['content'] for request in chat_provider)
    assert all('Best at window start: 100; target: 95.0' in request['messages'][0]['content'] for request in chat_provider)
    assert json.loads(config.result_file.read_text())['attempts'] == 41


async def test_empty_test_suite_completes_as_failure(config, botbox_script):
    (config.problem_dir / 'input_output.json').write_text('{"inputs":[],"outputs":[]}')
    botbox_script.advice.extend(['double'] * 4)
    botbox_script.solutions.extend([PASS] * 4)
    assert await run_experiment(config, on_delta=None) is None
    assert (await state(config, ExperimentDatabase(config.output)))['state'] == 'stopped'


async def test_failed_generation_diagnostic_does_not_count_as_solution(config):
    await saved_turn(config, stage='solutions_missing')
    write(config.t_dir(0,0) / 'run.json', '{"exit_code":-1}')
    assert (await fork_state(config, ExperimentDatabase(config.output)))['state'] == 'solutions_missing'


def test_process_exit_mid_ts_resumes_without_repeated_calls(config, tmp_path):
    """Kill the interpreter after four published Ts; resume in a new interpreter."""
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
                u_model='fake', t_model='fake', u_thinking='off', t_samples=3,
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
    if sys.argv[2] == 'crash' and len(list(config.output.glob('windows/*/forks/*/turns/*/ts/*/run.json'))) >= 4:
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
    assert len(list(config.output.glob('windows/*/forks/*/turns/*/ts/*/run.json'))) == 4
    resumed = subprocess.run([sys.executable, str(worker), str(tmp_path), 'resume'], capture_output=True, text=True, timeout=15)
    assert resumed.returncode == 0, resumed.stderr
    u_calls = list((tmp_path/'calls/U').rglob('messages.jsonl'))
    t_calls = list((tmp_path/'calls/T').rglob('count'))
    assert len(u_calls) == 4 and len(t_calls) == 12
    assert all(path.read_text() == '1' for path in [*u_calls, *t_calls, tmp_path/'calls/score'])


async def test_missing_generation_file_prevents_completed_turn(config):
    await saved_turn(config)
    (config.t_dir(0,0) / 'run.json').rename(config.t_dir(0,0) / '.unpublished-run')
    assert (await fork_state(config, ExperimentDatabase(config.output)))['state'] == 'solutions_missing'
    assert (await state(config, ExperimentDatabase(config.output)))['state'] == 'fork_round'
