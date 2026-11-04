"""Existing folders enter the same machine as fresh runs."""
import asyncio
import importlib
import json

import pytest

from conftest import FakeSession
from surprisals_experiment.sdk.run_experiment.actions.write_solutions.produce_code import produce_code
from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'


@pytest.mark.parametrize('boundary', ['advice', 'score', 'tests'])
async def test_restart_reuses_published_steps(config, botbox_script, chat_provider, monkeypatch, boundary):
    module = importlib.import_module('surprisals_experiment.sdk.run_experiment.run_experiment')
    config.max_u_turns = 1
    config.max_turns_without_improvement = 1
    botbox_script.advice.append('Double.')
    botbox_script.solutions.append(PASS)
    if boundary == 'advice':
        advice_module = importlib.import_module('surprisals_experiment.sdk.run_experiment.actions.write_advice')
        original = advice_module.save_advice

        def interrupt(*args):
            raise asyncio.CancelledError

        monkeypatch.setattr(advice_module, 'save_advice', interrupt)
    else:
        method = 'score_advice' if boundary == 'score' else 'run_tests'
        original = getattr(module, method)

        async def interrupt(*args, **kwargs):
            await original(*args, **kwargs)
            raise asyncio.CancelledError

        monkeypatch.setattr(module, method, interrupt)
    with pytest.raises(asyncio.CancelledError):
        await run_experiment(config, on_delta=None)
    if boundary == 'advice':
        assert not (config.advice_dir(0, 0) / 'advice.txt').exists()
        monkeypatch.setattr(advice_module, 'save_advice', original)
    else:
        published = (config.advice_dir(0, 0) / 'metadata.json' if boundary == 'score'
                     else config.t_dir(0, 0) / 'tests.json')
        saved = (published.read_bytes(), published.stat().st_mtime_ns)
        monkeypatch.setattr(module, method, original)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(chat_provider) == 1
    assert len(botbox_script.sessions) == 1
    if boundary != 'advice':
        assert (published.read_bytes(), published.stat().st_mtime_ns) == saved


async def test_pending_compaction_resumes_without_repeating_summary(config, botbox_script, chat_provider, monkeypatch):
    from surprisals_experiment.sdk.utils.u_chat import ChatSession
    config.max_u_turns = 2
    config.u_compact_chars = 1
    botbox_script.advice.extend(['Double.', 'Summary.', 'D.'])
    botbox_script.solutions.extend([PASS, PASS])
    original = ChatSession.record

    def record(self, message, **kwargs):
        if kwargs.get('reset'):
            raise asyncio.CancelledError
        return original(self, message, **kwargs)

    monkeypatch.setattr(ChatSession, 'record', record)
    with pytest.raises(asyncio.CancelledError):
        await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 2
    monkeypatch.setattr(ChatSession, 'record', original)
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 3
    assert 'Summary.' in chat_provider[-1]['messages'][1]['content']
    assert len(chat_provider[-1]['messages']) == 3


async def test_restart_reuses_surprisal_for_identical_advice(
    config, botbox_script, scorer_provider, monkeypatch,
):
    from surprisals_experiment.config import Config
    module = importlib.import_module('surprisals_experiment.sdk.run_experiment.run_experiment')
    config = Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1', 'max_u_turns': 2,
    }))
    scorer_provider.replies.append([('Double.', 7.0)])
    botbox_script.advice.extend(['Double.', 'Double.'])
    botbox_script.solutions.extend([PASS, PASS])
    original = module.write_solutions

    async def interrupt(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(module, 'write_solutions', interrupt)
    with pytest.raises(asyncio.CancelledError):
        await run_experiment(config, on_delta=None)
    monkeypatch.setattr(module, 'write_solutions', original)
    await run_experiment(Config(**config.model_dump()), on_delta=None)
    assert len(scorer_provider.requests) == 1
    assert json.loads(config.result_file.read_text())['best_measurement'] == 7.0


@pytest.mark.parametrize('action,artifact', [('write_feedback', 'feedback.txt'), ('write_result', 'result.json')])
@pytest.mark.parametrize('flush', [False, True])
async def test_restart_after_publication(config, botbox_script, chat_provider, monkeypatch, action, artifact, flush):
    module = importlib.import_module('surprisals_experiment.sdk.run_experiment.run_experiment')
    config.max_u_turns = 1
    config.u_flush = flush
    botbox_script.advice.append('Double.')
    botbox_script.solutions.append(PASS)
    original = getattr(module, action)

    def interrupt(*args, **kwargs):
        original(*args, **kwargs)
        raise asyncio.CancelledError

    monkeypatch.setattr(module, action, interrupt)
    with pytest.raises(asyncio.CancelledError):
        await run_experiment(config, on_delta=None)
    path = config.result_file if artifact == 'result.json' else config.attempt_dir(0) / artifact
    saved = (path.read_bytes(), path.stat().st_mtime_ns)
    monkeypatch.setattr(module, action, original)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert (path.read_bytes(), path.stat().st_mtime_ns) == saved
    assert len(chat_provider) == 1
    assert len(botbox_script.sessions) == 1


@pytest.mark.parametrize('flush,compact', [(False, 0), (True, 0), (False, 1)])
async def test_cli_sigterm_then_restart_keeps_finished_calls(
    config, botbox_script, chat_provider, monkeypatch, flush, compact,
):
    cli = importlib.import_module('surprisals_experiment.cli.main')
    monkeypatch.setattr(cli, 'find_dotenv', lambda **kw: 'mock.env')
    monkeypatch.setattr(cli, 'dotenv_values', lambda *a, **kw: {'OPENROUTER_API_KEY': 'test-key'})
    botbox_script.advice.extend(['Double the input.', *(['summary'] if compact else []), 'Double.', *(['summary two'] if compact else []), 'D.'])
    botbox_script.solutions.extend([PASS] * 6)
    original = FakeSession.message
    started = asyncio.Event()

    async def message(self, text):
        if self.mounts['/solution'].parent.name == '1' and self.mounts['/solution'].parents[2].name == '1':
            started.set()
            await asyncio.Event().wait()
        await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', message)
    args = ['--output', str(config.output), '--t-samples', '2', '--t-pool-size', '1',
            '--max-u-turns', '3', '--u-compact-chars', str(compact),
            'problem', '--u-flush', str(int(flush)), str(config.problem_dir)]
    task = asyncio.create_task(cli.main(args))
    try:
        await asyncio.wait_for(started.wait(), 10)
        import signal
        signal.raise_signal(signal.SIGTERM)
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    saved = (config.t_dir(1, 0) / 'run.json').read_bytes()
    assert not (config.t_dir(1, 1) / 'run.json').exists()
    completed_before = [session.mounts['/solution'] for session in botbox_script.sessions[:-1]]
    requests = len(chat_provider)
    sessions_before = len(botbox_script.sessions)
    monkeypatch.setattr(FakeSession, 'message', original)
    await asyncio.wait_for(cli.main(args), 10)
    assert len(chat_provider) == requests + (2 if compact else 1)
    assert (config.t_dir(1, 0) / 'run.json').read_bytes() == saved
    assert len(botbox_script.sessions) == 7
    resumed = [session.mounts['/solution'] for session in botbox_script.sessions[sessions_before:]]
    assert resumed[0] == config.t_dir(1, 1) / 'src'
    assert not set(completed_before) & set(resumed)
    assert json.loads(config.result_file.read_text())['attempts'] == 3
    messages = chat_provider[-1]['messages']
    if flush:
        assert len(messages) == 2
        assert 'Double the input.' in messages[-1]['content']
    elif compact:
        assert len(messages) == 3
        assert '<best_successful_advice>\nDouble.\n</best_successful_advice>' in messages[1]['content']
    else:
        assert [m['content'] for m in messages if m['role'] == 'assistant'] == ['Double the input.', 'Double.']
    assert not botbox_script.solutions


async def test_restart_feedback_recovers_sources_from_solution_directory(config, botbox_script, chat_provider, monkeypatch):
    module = importlib.import_module('surprisals_experiment.sdk.run_experiment.run_experiment')
    config.max_u_turns = 2
    botbox_script.advice.extend(['First.', 'Second.'])
    botbox_script.solutions.extend([
        'print(0)\n', PASS,
    ])
    original = module.run_tests

    async def interrupt(*args, **kwargs):
        await original(*args, **kwargs)
        raise asyncio.CancelledError

    monkeypatch.setattr(module, 'run_tests', interrupt)
    with pytest.raises(asyncio.CancelledError):
        await run_experiment(config, on_delta=None)
    monkeypatch.setattr(module, 'run_tests', original)
    await run_experiment(config, on_delta=None)
    assert 'print(0)' in chat_provider[1]['messages'][-1]['content']
    assert json.loads((config.t_dir(0, 0) / 'run.json').read_text()) == {'exit_code': 0}


async def test_restart_incomplete_folder_gets_full_timeout_budget(config, botbox_script, monkeypatch):
    config.t_sample_retries = 2
    config.t_sample_timeout = .01
    directory = config.t_dir(0, 0)
    directory.mkdir(parents=True)
    (directory / 'timeouts.txt').write_text('previous interrupted call timeout\n')
    botbox_script.advice.append('Double.')

    async def message(self, text):
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', message)
    await run_experiment(config, on_delta=None)
    assert len(botbox_script.sessions) == 3
    assert len((directory / 'timeouts.txt').read_text().splitlines()) == 3
    assert (directory / 'tests.json').exists()
    assert json.loads(config.result_file.read_text())['attempts'] == 1


@pytest.mark.parametrize('retries', [0, 2])
async def test_each_call_gets_full_timeout_budget(config, botbox_script, monkeypatch, tmp_path, retries, no_retry_wait):
    config.t_sample_retries = retries
    config.t_sample_timeout = .01
    folder = tmp_path / 'unnumbered'

    async def message(self, text):
        assert not list(self.mounts['/solution'].iterdir())
        (self.mounts['/solution'] / 'partial.py').write_text('partial')
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', message)
    for call in range(2):
        source = await produce_code(config, output=folder, advice='Double.')
        assert len(botbox_script.sessions) == (call + 1) * (retries + 1)
        assert all(session.closed for session in botbox_script.sessions)
        assert list(source.iterdir()) == []
        assert len((folder / 'timeouts.txt').read_text().splitlines()) == retries + 1

    assert not no_retry_wait.await_args_list
