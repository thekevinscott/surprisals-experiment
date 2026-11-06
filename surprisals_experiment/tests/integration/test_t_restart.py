"""A run killed while T is writing code restarts cleanly."""

import asyncio
import json
from unittest.mock import patch

from fake_llm import KILL, U, FakeLLM, Fork, Run, T, Turn, Window

from surprisals_experiment.sdk import run_experiment

DOUBLE = {'main.py': 'print(int(input()) * 2)\n'}
real_sleep = asyncio.sleep


async def no_wait(delay, *args, **kwargs):
    await real_sleep(0)


async def test_restart_after_killing_t(config):
    session = Run(
        Window(Fork(Turn(U('Double it.'), T(DOUBLE, KILL)))),
        Window(Fork(Turn(U('Double it.'), T(DOUBLE)))),
    )
    events = []
    with FakeLLM(session) as llm, patch('asyncio.sleep', no_wait):
        with llm.killed():
            await run_experiment(config, on_delta=None)
        await run_experiment(config, on_delta=None, on_t_delta=lambda *event: events.append(event))
    assert llm.unused_replies == 0
    assert [text for _, kind, text in events if kind == 'retry'] == []
    assert json.loads(config.result_file.read_text())['success']
