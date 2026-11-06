"""A T sample killed mid-generation resumes without losing what it wrote."""

import asyncio
import json

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'
PASS_AGAIN = 'print(2 * int(input()))\n'


def files(output):
    return {path: path.read_bytes() for path in output.rglob('*') if path.is_file()}


async def test_t_killed_mid_generation_resumes_without_losing_its_output(config, botbox_script):
    botbox_script.advice.extend(['Double it.'] * 2)
    botbox_script.solutions.extend([PASS, PASS_AGAIN, PASS_AGAIN])
    botbox_script.t_seconds = 1
    run = asyncio.create_task(run_experiment(config, on_delta=None))
    while not any(config.output.glob('windows/0/forks/0/turns/0/ts/0/**/main.py')):
        await asyncio.sleep(.01)
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    before = files(config.output)

    await run_experiment(config, on_delta=None)
    after = files(config.output)
    for path, content in before.items():
        assert after.get(path, b'').startswith(content), path
    assert json.loads(config.result_file.read_text())['success']
