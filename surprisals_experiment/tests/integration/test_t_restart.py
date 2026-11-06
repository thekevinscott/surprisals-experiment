"""A run killed while T is writing code restarts cleanly."""

import json

from utils.llm_replies import U, Fork, Run, T, Turn, Window

from surprisals_experiment.sdk import run_experiment


async def test_restart_after_killing_t(config, fake_llm, no_retry_wait):
    double = {'main.py': 'print(int(input()) * 2)\n'}
    killed_t = T(double)
    llm = fake_llm(Run(
        Window(Fork(Turn(U('Double it.'), killed_t))),
        Window(Fork(Turn(U('Double it.'), T(double)))),
    ))
    llm.kill_after(killed_t)
    events = []
    with llm.killed():
        await run_experiment(config, on_delta=None)
    await run_experiment(config, on_delta=None, on_t_delta=lambda *event: events.append(event))
    assert llm.unused_replies == 0
    assert [text for _, kind, text in events if kind == 'retry'] == []
    assert json.loads(config.result_file.read_text())['success']
