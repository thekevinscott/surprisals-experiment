"""A T sample killed mid-generation resumes cleanly."""

import asyncio
import json

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'


async def test_t_killed_mid_generation_resumes_without_a_retry(config, botbox_script):
    botbox_script.advice.extend(['Double it.'] * 2)
    botbox_script.solutions.extend([asyncio.Event(), PASS, PASS])
    run = asyncio.create_task(run_experiment(config, on_delta=None))
    while not botbox_script.sessions:
        await asyncio.sleep(0)
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run

    # A retry waits 10 seconds before trying again.
    await asyncio.wait_for(run_experiment(config, on_delta=None), 5)
    assert len(botbox_script.sessions) == 3
    assert json.loads(config.result_file.read_text())['success']
