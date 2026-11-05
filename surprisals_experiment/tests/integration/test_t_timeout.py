"""Hung T samples retry and real CLI SIGTERM cancels both model phases."""
import asyncio
import json
from derived_prompt import derived_prompt
import signal
from contextlib import nullcontext
from unittest.mock import patch
import httpx2
import pytest

from openai import AsyncOpenAI
from conftest import FakeSession
from run_one_window import run_one_window
from surprisals_experiment.cli.main import main

async def test_retries_a_hung_sample_once_with_a_fresh_t(config, botbox_script, monkeypatch):
    config.t_samples = 3
    config.t_sample_timeout = .1
    config.t_sample_retries = 1
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
    await asyncio.wait_for(run_one_window(config, on_delta=None), 5)
    assert len(botbox_script.sessions) == 4
    assert all(s.closed for s in botbox_script.sessions)
    assert json.loads(config.result_file.read_text())['success']
    assert (config.t_dir(0, 1) / 'timeouts.txt').read_text() == 'T exceeded 0.1 seconds\n'
    assert not (config.attempt_dir(0) / 'error.txt').exists()
    assert 'timed out' not in (await derived_prompt(config))


async def test_counts_a_sample_that_hangs_twice_as_failed_and_keeps_running(config, botbox_script, monkeypatch):
    config.max_u_turns = 2
    config.t_samples = 3
    config.t_sample_timeout = .1
    config.t_sample_retries = 1
    botbox_script.advice.extend(['Double the input.', 'Double.'])
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 5)
    original = FakeSession.message

    async def message(self, text):
        output = self.mounts['/solution']
        if output.parents[2].name == '1' and output.parent.name == '2':
            await asyncio.Event().wait()
        return await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', message)
    await asyncio.wait_for(run_one_window(config, on_delta=None), 5)
    assert len(botbox_script.sessions) == 7
    assert all(s.closed for s in botbox_script.sessions)
    assert not (config.attempt_dir(1) / 'error.txt').exists()
    assert (config.t_dir(1, 2) / 'timeouts.txt').read_text().count('exceeded 0.1 seconds') == 2
    tests = json.loads((config.t_dir(1, 2) / 'tests.json').read_text())
    assert tests['passed'] == 0 and not tests['all_passed']
    result = json.loads(config.result_file.read_text())
    assert result['success'] and result['attempts'] == 2
    assert result['solution'] == str(config.t_dir(0, 0) / 'src')


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
    await run_one_window(config, on_delta=None)
    assert json.loads(config.result_file.read_text())['success']
    assert len(botbox_script.sessions) == 3
    assert all(s.closed for s in botbox_script.sessions)
    assert not list(config.output.glob('windows/*/forks/*/turns/*/ts/*/timeouts.txt'))


async def test_does_not_retry_with_a_zero_budget(config, botbox_script, monkeypatch):
    config.t_sample_retries = 0
    config.t_sample_timeout = .05
    botbox_script.advice.append('Double.')

    async def message(self, text):
        assert not list(self.mounts['/solution'].iterdir())
        (self.mounts['/solution'] / 'partial.py').write_text('partial')
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', message)
    await asyncio.wait_for(run_one_window(config, on_delta=None), 5)
    assert len(botbox_script.sessions) == 1
    assert all(s.closed for s in botbox_script.sessions)
    assert not json.loads(config.result_file.read_text())['success']
    assert len((config.t_dir(0, 0) / 'timeouts.txt').read_text().splitlines()) == 1
    assert not list((config.t_dir(0, 0) / 'src').iterdir())
    assert json.loads((config.t_dir(0, 0) / 'tests.json').read_text())['passed'] == 0
    assert json.loads((config.output / 'settings.json').read_text())['t_sample_retries'] == 0


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
    else:
        monkeypatch.setattr(FakeSession, 'message', block)
    with (patch('surprisals_experiment.sdk.utils.u_chat.opener.AsyncOpenAI', client)
          if phase == 'U' else nullcontext()):
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
            assert config.u_transcripts.joinpath('messages.jsonl').exists()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
