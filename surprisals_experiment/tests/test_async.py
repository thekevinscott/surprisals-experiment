"""Native model calls cancel directly; blocking evaluation finishes before cleanup."""

import asyncio
import importlib
import threading

import pytest

from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment


def describe_async_orchestration():
    @pytest.mark.parametrize('phase', ['startup', 'u_message', 't_message'])
    async def it_cancels_native_sessions_and_keeps_u_artifacts(
        config, botbox_script, monkeypatch, phase,
    ):
        botbox_script.advice.append('double it')
        botbox_script.solutions.append('print(int(input()) * 2)\n')
        started = asyncio.Event()
        method = '__aenter__' if phase == 'startup' else 'message'
        original = getattr(FakeSession, method)

        async def block(self, *args):
            if phase == 'startup' or self.is_u == (phase == 'u_message'):
                started.set()
                await asyncio.Event().wait()
            return await original(self, *args)

        monkeypatch.setattr(FakeSession, method, block)
        task = asyncio.create_task(run_experiment(config, on_delta=None))
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert not config.result_file.exists()
        assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()
        if phase != 'startup':
            assert all(session.closed for session in botbox_script.sessions)
            assert (config.u_transcripts / 'session.jsonl').exists()
            assert config.u_proxy_log.exists()

    async def it_waits_for_evaluation_before_cancellation_cleanup(
        config, botbox_script, monkeypatch,
    ):
        botbox_script.advice.append('double it')
        botbox_script.solutions.append('print(int(input()) * 2)\n')
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        started = asyncio.Event()
        release = threading.Event()
        target = importlib.import_module('surprisals_experiment.sdk.run_test_suite.run_test_suite')
        original = target.run_case

        def block(*args, **kwargs):
            assert threading.get_ident() != loop_thread
            loop.call_soon_threadsafe(started.set)
            assert release.wait(5), 'Event loop did not release evaluation'
            return original(*args, **kwargs)

        monkeypatch.setattr(target, 'run_case', block)
        task = asyncio.create_task(run_experiment(config, on_delta=None))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert all(session.closed for session in botbox_script.sessions)
        assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()
        assert not config.result_file.exists()
        assert (config.u_transcripts / 'session.jsonl').exists()
        assert config.u_proxy_log.exists()
