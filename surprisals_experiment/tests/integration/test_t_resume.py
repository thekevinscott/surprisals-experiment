"""A T sample killed mid-generation resumes cleanly."""

import asyncio
import json

import pytest

from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'


async def test_t_killed_mid_generation_resumes_without_a_retry(
    config, botbox_script, monkeypatch, no_retry_wait,
):
    botbox_script.advice.extend(['Double it.'] * 2)
    botbox_script.solutions.extend([PASS] * 2)
    original = FakeSession.message

    async def killed(self, text):
        (self.mounts['/solution'] / 'partial.py').write_text('partial')
        raise asyncio.CancelledError

    monkeypatch.setattr(FakeSession, 'message', killed)
    with pytest.raises(asyncio.CancelledError):
        await run_experiment(config, on_delta=None)

    monkeypatch.setattr(FakeSession, 'message', original)
    await run_experiment(config, on_delta=None)
    no_retry_wait.assert_not_awaited()
    assert len(botbox_script.sessions) == 3
    assert json.loads(config.result_file.read_text())['success']
