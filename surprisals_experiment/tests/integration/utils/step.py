"""Run the experiment once against replies, then assert its calls, files, logs and outcome exactly.

`...` anywhere in an expectation means "present, not checked". Expected file contents are
str (text), bytes, dict (JSON) or list (JSON lines).
"""

import asyncio
import json

from surprisals_experiment.sdk import run_experiment

from utils.deterministic import deterministic
from utils.run_files import run_files


def masked(expected, actual):
    if expected is ...:
        return ...
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {key: masked(expected[key], value) if key in expected else value for key, value in actual.items()}
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)) and len(expected) == len(actual):
        return type(actual)(masked(e, a) for e, a in zip(expected, actual))
    return actual


def decoded(expected, content):
    if isinstance(expected, str):
        return content.decode()
    if isinstance(expected, dict):
        return masked(expected, json.loads(content))
    if isinstance(expected, list):
        return masked(expected, [json.loads(line) for line in content.splitlines()])
    return masked(expected, content)


def described(outcome):
    return (type(outcome), str(outcome)) if isinstance(outcome, BaseException) else outcome


async def step(config, fake_llm, replies, *, calls, files, logs, outcome, kill_after=None):
    llm = fake_llm(replies)
    if kill_after is not None:
        llm.kill_after(kill_after)
    events = []

    def log(*event):
        events.append(event)

    with deterministic():
        try:
            result = await run_experiment(config, on_delta=log, on_t_delta=log)
        except (Exception, asyncio.CancelledError) as error:
            if llm.task.cancelling():
                llm.task.uncancel()
            result = error
    assert described(result) == described(outcome)
    assert masked(calls, llm.calls) == calls
    assert events == logs
    actual = run_files(config.output)
    assert {path: decoded(files[path], content) if path in files else content
            for path, content in actual.items()} == files
    assert llm.unused_replies == 0
    assert all(box.exited for box in llm.boxes)
