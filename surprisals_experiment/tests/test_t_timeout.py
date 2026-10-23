"""Timeout and SIGTERM unwind the real orchestration through mocked sessions."""

import asyncio
import importlib
import json
import signal

import pytest
from pydantic import ValidationError

from conftest import FakeSession
from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.cli.main import main


def describe_t_sample_timeout():
    @pytest.mark.parametrize('seconds', [0, -1])
    def it_requires_a_positive_limit(config, seconds):
        with pytest.raises(ValidationError):
            Config(**(config.model_dump() | {'t_sample_timeout': seconds}))

    def it_defaults_to_fifteen_minutes(config):
        assert config.t_sample_timeout == 900

    async def it_aborts_a_hung_batch_and_preserves_the_previous_best(config, botbox_script, monkeypatch):
        config.max_u_turns = 2
        config.t_samples = 3
        config.t_sample_timeout = .1
        botbox_script.advice.extend(['Double the input.', 'Double.'])
        botbox_script.solutions.extend(['print(int(input()) * 2)'] * 3)
        original = FakeSession.message

        async def message(self, text):
            if not self.is_u and self.mounts['/solution'].parents[2].name == '1':
                await asyncio.Event().wait()
            return await original(self, text)

        monkeypatch.setattr(FakeSession, 'message', message)
        with pytest.raises(RuntimeError, match=r'T sample \d exceeded 0.1 seconds'):
            await asyncio.wait_for(run_experiment(config, on_delta=None), 5)
        assert all(s.closed for s in botbox_script.sessions)
        assert len(botbox_script.t_sessions) == 6
        assert 'exceeded 0.1 seconds' in (config.attempt_dir(1) / 'error.txt').read_text()
        assert not (config.attempt_dir(1) / 'feedback.txt').exists()
        assert not list(config.attempt_dir(1).glob('t_samples/*/tests.json'))
        result = json.loads(config.result_file.read_text())
        assert result['success'] and result['attempts'] == 1
        assert result['solution'] == str(config.t_dir(0, 0) / 'src')
        assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()

    async def it_gives_queued_samples_their_own_full_budget(config, botbox_script, monkeypatch):
        config.t_samples = 3
        config.t_pool_size = 1
        config.t_sample_timeout = .2
        botbox_script.advice.append('Double.')
        botbox_script.solutions.extend(['print(int(input()) * 2)'] * 3)
        original = FakeSession.message

        async def message(self, text):
            if not self.is_u:
                await asyncio.sleep(.1)
            return await original(self, text)

        monkeypatch.setattr(FakeSession, 'message', message)
        await run_experiment(config, on_delta=None)
        assert json.loads(config.result_file.read_text())['success']
        assert all(s.closed for s in botbox_script.sessions)

    @pytest.mark.parametrize('phase', ['U', 'T'])
    async def it_cancels_and_cleans_up_on_sigterm(config, botbox_script, monkeypatch, phase):
        module = importlib.import_module('surprisals_experiment.cli.main')
        monkeypatch.setattr(module, 'find_dotenv', lambda **kw: 'mock.env')
        monkeypatch.setattr(module, 'dotenv_values', lambda *a, **kw: {'OPENROUTER_API_KEY': 'test-key'})
        botbox_script.advice.append('Double.')
        started = asyncio.Event()
        original = FakeSession.message

        async def message(self, text):
            if self.is_u == (phase == 'U'):
                started.set()
                await asyncio.Event().wait()
            return await original(self, text)

        monkeypatch.setattr(FakeSession, 'message', message)
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
            assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
