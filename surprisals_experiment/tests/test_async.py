"""The sync bridge must yield to the event loop and clean up after cancellation."""

import asyncio
import importlib
import threading

import pytest

from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment


def describe_async_orchestration():
    @pytest.mark.parametrize('phase', ['startup', 'u_message', 't_message', 'evaluation'])
    async def it_waits_for_blocking_work_before_cancellation_cleanup(
        config, botbox_script, monkeypatch, phase,
    ):
        botbox_script.advice.append('double it')
        botbox_script.solutions.append('print(int(input()) * 2)\n')
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        started = asyncio.Event()
        release = threading.Event()
        if phase == 'startup':
            target = importlib.import_module('surprisals_experiment.sdk.utils.botbox_session').Botbox
            name = 'session'
        elif phase == 'evaluation':
            target = importlib.import_module('surprisals_experiment.sdk.run_test_suite.run_test_suite')
            name = 'run_case'
        else:
            target, name = FakeSession, 'message'
        original = getattr(target, name)

        def block(*args, **kwargs):
            if phase in ('u_message', 't_message') and args[0].is_u != (phase == 'u_message'):
                return original(*args, **kwargs)
            assert threading.get_ident() != loop_thread
            loop.call_soon_threadsafe(started.set)
            assert release.wait(5), 'Event loop did not release the blocking operation'
            return original(*args, **kwargs)

        monkeypatch.setattr(target, name, block)
        task = asyncio.create_task(run_experiment(config, on_delta=None))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done(), 'Cancellation must not race resource cleanup against the worker'
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert botbox_script.sessions
        assert all(session.closed for session in botbox_script.sessions)
        assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()
        assert not config.result_file.exists()
        if phase != 'startup':
            assert (config.u_transcripts / 'session.jsonl').exists()
            assert config.u_proxy_log.exists()
