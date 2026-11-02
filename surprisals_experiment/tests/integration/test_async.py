"""Model calls and testcase subprocesses cancel before session cleanup."""

import asyncio
import importlib
import os

import pytest

from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_chat import ChatSession


def describe_async_orchestration():
    @pytest.mark.parametrize('phase', ['startup', 'u_message', 't_message'])
    async def it_cancels_native_sessions_and_keeps_u_artifacts(
        config, botbox_script, monkeypatch, phase,
    ):
        botbox_script.advice.append('double it')
        botbox_script.solutions.append('print(int(input()) * 2)\n')
        started = asyncio.Event()
        owner, method = {
            'startup': (FakeSession, '__aenter__'), 'u_message': (ChatSession, 'prompt'),
            't_message': (FakeSession, 'message'),
        }[phase]
        original = getattr(owner, method)

        async def block(self, *args, **kwargs):
            started.set()
            await asyncio.Event().wait()
            return await original(self, *args, **kwargs)

        monkeypatch.setattr(owner, method, block)
        task = asyncio.create_task(run_experiment(config, on_delta=None))
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert not config.result_file.exists()
        assert not botbox_script.u_workspaces[0].exists()
        assert (config.u_transcripts / 'messages.jsonl').exists()
        if phase != 'startup':
            assert all(session.closed for session in botbox_script.sessions)

    @pytest.mark.parametrize('outcome', ['cancel', 'timeout'])
    async def it_reaps_evaluation_before_session_cleanup(config, botbox_script, monkeypatch, outcome):
        config.max_u_turns = 1
        suite = importlib.import_module('surprisals_experiment.sdk.run_test_suite.run_test_suite')
        monkeypatch.setattr(suite, 'TEST_TIMEOUT_SECONDS', 0.5 if outcome == 'timeout' else 30)
        botbox_script.advice.append('double it')
        botbox_script.solutions.append(
            "import os, time\nfrom pathlib import Path\n"
            "Path('pid').write_text(str(os.getpid()))\ntime.sleep(60)\n"
        )
        task = asyncio.create_task(run_experiment(config, on_delta=None))
        pid_file = config.t_dir(0, 0) / 'src' / 'pid'
        try:
            async with asyncio.timeout(5):
                while not pid_file.exists():
                    await asyncio.sleep(0.01)
            pid = int(pid_file.read_text())
            if outcome == 'cancel':
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=5)
                assert not config.result_file.exists()
            else:
                await asyncio.wait_for(task, timeout=5)
                assert config.result_file.exists()
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
        assert all(session.closed for session in botbox_script.sessions)
        assert not botbox_script.u_workspaces[0].exists()
        assert (config.u_transcripts / 'messages.jsonl').exists()
