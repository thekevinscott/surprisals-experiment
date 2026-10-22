"""Bounded T concurrency, ordered results, and failure cleanup."""

import asyncio
import json

import pytest
from pydantic import ValidationError

from conftest import FakeSession
from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.prompt_t_to_produce_code import prompt_t_to_produce_code
from surprisals_experiment.sdk.run_test_suite import run_test_suite_for_ts


def describe_t_pool():
    @pytest.mark.parametrize('size', [1, 2, 3, 8])
    async def it_bounds_concurrency_and_retains_sample_order(config, botbox_script, monkeypatch, size):
        config.t_samples = 5
        config.t_pool_size = size
        botbox_script.solutions.extend(['print(6)', 'print(0)', 'print(6)', 'print(0)', 'print(6)'])
        started = [asyncio.Event() for _ in range(5)]
        release = [asyncio.Event() for _ in range(5)]
        finished = [asyncio.Event() for _ in range(5)]
        active = peak = 0
        completion = []
        original = FakeSession.message

        async def message(self, text):
            nonlocal active, peak
            sample = int(self.mounts['/solution'].parent.name)
            active += 1
            peak = max(peak, active)
            try:
                reply = await original(self, text)
                started[sample].set()
                await release[sample].wait()
                completion.append(sample)
                return reply
            finally:
                active -= 1
                finished[sample].set()

        monkeypatch.setattr(FakeSession, 'message', message)
        task = asyncio.create_task(prompt_t_to_produce_code(
            config, attempt=0, advice='double it',
            snapshot=config.output / 'snapshots',
        ))
        try:
            async with asyncio.timeout(5):
                capacity = min(size, 5)
                await asyncio.gather(*(event.wait() for event in started[:capacity]))
                assert not any(event.is_set() for event in started[capacity:])
                for sample in reversed(range(capacity)):
                    release[sample].set()
                    await finished[sample].wait()
                for event in release:
                    event.set()
                solutions = await task
            assert not list(config.output.glob("attempts/*/t_samples/*/tests.json"))
            results = await run_test_suite_for_ts(config, solutions, {"inputs": ["3\n"], "outputs": ["6\n"]})
            assert peak == capacity
            assert completion[:capacity] == list(reversed(range(capacity)))
            assert [result.all_passed for result in results] == [True, False, True, False, True]
            assert [session.messages for session in botbox_script.t_sessions] == [['double it']] * 5
            for sample, result in enumerate(results):
                saved = json.loads((config.t_dir(0, sample) / 'tests.json').read_text())
                assert saved['all_passed'] == result.all_passed
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @pytest.mark.parametrize('outcome', ['error', 'cancel'])
    async def it_closes_all_t_sessions_before_u_on_failure(config, botbox_script, monkeypatch, outcome):
        config.t_samples = 5
        botbox_script.advice.append('double it')
        full = asyncio.Event()
        fail = asyncio.Event()
        started = 0
        original = FakeSession.message

        async def message(self, text):
            nonlocal started
            if self.is_u:
                return await original(self, text)
            started += 1
            if started == 3:
                full.set()
            try:
                if self.mounts['/solution'].parent.name == '0':
                    await fail.wait()
                    raise RuntimeError('provider unavailable')
                await asyncio.Event().wait()
            finally:
                assert not botbox_script.u_sessions[0].closed

        monkeypatch.setattr(FakeSession, 'message', message)
        task = asyncio.create_task(run_experiment(config, on_delta=None))
        try:
            await asyncio.wait_for(full.wait(), timeout=5)
            if outcome == 'error':
                fail.set()
                with pytest.raises(RuntimeError, match='provider unavailable'):
                    await asyncio.wait_for(task, timeout=5)
                assert 'provider unavailable' in (config.attempt_dir(0) / 'error.txt').read_text()
            else:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=5)
            assert all(session.closed for session in botbox_script.sessions)
            assert not config.result_file.exists()
            assert not (config.attempt_dir(0) / 'feedback.txt').exists()
            assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @pytest.mark.parametrize('size', [0, -1])
    def it_rejects_nonpositive_sizes(config, size):
        with pytest.raises(ValidationError):
            Config(**(config.model_dump() | {'t_pool_size': size}))

    def it_defaults_to_three(config):
        assert config.t_pool_size == 3
