"""Timeouts leave generation unfinished; SIGTERM cancels both model phases."""

from surprisals_experiment.sdk.turn import Turn
import asyncio
import importlib
import json
import signal
import httpx2
import pytest
from openai import AsyncOpenAI
from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.cli.main import main

async def test_timeout_leaves_same_next_step_with_a_fresh_t(config, botbox_script, monkeypatch):
    config.t_samples = 3
    config.t_sample_timeout = .1
    botbox_script.advice.append('Double.')
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 3)
    original = FakeSession.message
    hung = []

    async def message(self, text):
        if self.mounts['/solution'].parent.name == '1' and not hung:
            hung.append(self)
            (self.mounts['/solution'] / 'partial.py').write_text('partial')
            await asyncio.Event().wait()
        assert not (self.mounts['/solution'] / 'partial.py').exists()
        return await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', message)
    await asyncio.wait_for(run_experiment(config, on_delta=None), 5)
    assert len(botbox_script.sessions) == 4
    assert all(s.closed for s in botbox_script.sessions)
    assert json.loads(config.result_file.read_text())['success']
    assert 'TimeoutError' in (config.attempt_dir(0) / 'error.txt').read_text()
    assert 'timed out' not in (config.attempt_dir(0) / 'feedback.txt').read_text()


async def test_gives_queued_samples_their_own_full_budget(config, botbox_script, monkeypatch):
    config.t_samples = 3
    config.t_pool_size = 1
    config.t_sample_timeout = .2
    botbox_script.advice.append('Double.')
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 3)
    original = FakeSession.message

    async def message(self, text):
        await asyncio.sleep(.1)
        return await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', message)
    await run_experiment(config, on_delta=None)
    assert json.loads(config.result_file.read_text())['success']
    assert len(botbox_script.sessions) == 3
    assert all(s.closed for s in botbox_script.sessions)
    assert not list(config.output.glob('windows/*/forks/*/turns/*/ts/*/timeouts.txt'))


async def test_permanent_timeout_has_no_completion_or_budget(config, botbox_script, monkeypatch):
    config.t_sample_timeout = .01
    botbox_script.advice.append('Double.')
    reached = asyncio.Event()
    calls = 0

    async def message(self, text):
        nonlocal calls
        calls += 1
        assert not (config.t_dir(0, 0) / 'run.json').exists()
        assert not list(self.mounts['/solution'].iterdir())
        (self.mounts['/solution'] / 'partial.py').write_text('partial')
        if calls >= 6:
            reached.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', message)
    task = asyncio.create_task(run_experiment(config, on_delta=None))
    try:
        await asyncio.wait_for(reached.wait(), 5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not (config.t_dir(0, 0) / 'run.json').exists()
    assert not (config.t_dir(0, 0) / 'tests.json').exists()
    assert not config.result_file.exists()
    assert all(s.closed for s in botbox_script.sessions)


@pytest.mark.parametrize('phase', ['U', 'T'])
async def test_cancels_and_cleans_up_on_sigterm(config, botbox_script, monkeypatch, tmp_path, phase):
    (tmp_path / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
    monkeypatch.chdir(tmp_path)
    botbox_script.advice.append('Double.')
    started = asyncio.Event()

    async def block(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    if phase == 'U':
        def client(**kwargs):
            return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(
                transport=httpx2.MockTransport(block)))
        module = importlib.import_module('surprisals_experiment.sdk.utils.u_chat.open_u_chat')
        monkeypatch.setattr(module, 'AsyncOpenAI', client)
    else:
        monkeypatch.setattr(FakeSession, 'message', block)
    task = asyncio.create_task(main([
        '--output', str(config.output), '--t-samples', '1', '--t-sample-timeout', '1.5',
        'problem', str(config.problem_dir),
    ]))
    try:
        await asyncio.wait_for(started.wait(), 5)
        signal.raise_signal(signal.SIGTERM)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert all(s.closed for s in botbox_script.sessions)
        assert Turn(config, 0).u_transcripts.joinpath('messages.jsonl').exists()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
