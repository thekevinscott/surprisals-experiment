"""Model calls and testcase subprocesses cancel before session cleanup."""

import asyncio
import os

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

    @pytest.mark.parametrize('outcome', ['cancel', 'timeout'])
    async def it_reaps_evaluation_before_session_cleanup(config, botbox_script, outcome):
        config.max_u_turns = 1
        config.test_timeout_seconds = 0.5 if outcome == 'timeout' else 30
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
        assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()
        assert (config.u_transcripts / 'session.jsonl').exists()
        assert config.u_proxy_log.exists()
