"""Failures return control to disk-derived state; cancellation still stops work."""

from surprisals_experiment.sdk.turn import Turn

import asyncio
import importlib
import json
import os

import httpx2
import pytest
from botbox import RunResult

from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_chat import open_u_chat

PASS = 'print(int(input()) * 2)'
PROVIDER_ERROR = {
    'deltas': [{'role': 'assistant', 'content': 'partial', 'reasoning': 'partial reasoning'}],
    'finish': 'error', 'finish_choice': {'error': {'message': 'upstream failed', 'code': 502}},
}


def transcript(config):
    return [json.loads(line) for line in
            (Turn(config, 0).u_transcripts / 'messages.jsonl').read_text().splitlines()]


def length_reply(tokens=None):
    reply = {'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': 'length'}
    if tokens is not None:
        reply['usage'] = {'prompt_tokens': 10, 'completion_tokens': tokens, 'total_tokens': tokens + 10,
                          'completion_tokens_details': {'reasoning_tokens': tokens - 1}}
    return reply


@pytest.mark.parametrize('failure', [
    pytest.param({'deltas': [{'role': 'assistant', 'reasoning': 'Hmm: what about'}], 'finish': 'stop'},
                 id='thinking-only-stop'),
    pytest.param({'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': 'content_filter'},
                 id='content-filter'),
    pytest.param(httpx2.ConnectError('Connection error'), id='connection-error'),
    pytest.param({'deltas': [{'role': 'assistant', 'content': 'partial'}],
                  'finish': None, 'drop_stream': True}, id='dropped-stream'),
    pytest.param(PROVIDER_ERROR, id='provider-error'),
    pytest.param(length_reply(20), id='output-limit'),
])
async def test_failed_reply_reenters_same_state_with_original_history(
    config, botbox_script, chat_provider, no_backoff, failure,
):
    botbox_script.advice.extend([failure, 'Use a loop'])
    botbox_script.solutions.append(PASS)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(chat_provider) == 2
    assert chat_provider[0]['messages'] == chat_provider[1]['messages']
    no_backoff.assert_not_awaited()
    messages = transcript(config)
    if isinstance(failure, dict):
        partial = next(m for m in messages if m.get('content') == 'partial' or
                       m.get('reasoning') == 'Hmm: what about')
        if failure.get('finish') == 'error':
            assert partial['reasoning'] == 'partial reasoning'
            assert partial['provider_error']['choices'][0]['error'] == failure['finish_choice']['error']
    assert any(m.get('content') == 'Use a loop' for m in messages)


async def test_credential_proxy_failure_returns_to_state(config, botbox_script, monkeypatch, no_backoff):
    module = importlib.import_module('surprisals_experiment.sdk.utils.botbox_run')
    builds = []

    class FailingEntry(module.Botbox):
        async def build(self):
            builds.append(self)
            if len(builds) == 1:
                raise RuntimeError('botbox credential proxy did not start:\n')
            return await super().build()

    monkeypatch.setattr(module, 'Botbox', FailingEntry)
    botbox_script.advice.append('Use a loop')
    botbox_script.solutions.append(PASS)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(builds) == 2
    no_backoff.assert_not_awaited()


async def test_one_failed_reply_preserves_partial_evidence(config, botbox_script, chat_provider):
    botbox_script.advice.append(PROVIDER_ERROR)
    with pytest.raises(RuntimeError, match='U chat provider error'):
        async with open_u_chat(Turn(config, 0)) as session:
            await session.prompt('question')
    assert len(chat_provider) == 1
    assert transcript(config)[-1]['content'] == 'partial'
    assert transcript(config)[-1]['_complete'] is False


async def test_run_continues_past_former_u_budget(config, botbox_script, chat_provider):
    botbox_script.advice.extend([length_reply()] * 12 + ['Use a loop'])
    botbox_script.solutions.append(PASS)
    assert await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 13
    assert all(request['messages'] == chat_provider[0]['messages'] for request in chat_provider)


async def test_permanent_provider_failure_remains_cancellable(config, botbox_script, monkeypatch):
    module = importlib.import_module('surprisals_experiment.sdk.utils.u_chat.reply')
    reached = asyncio.Event()
    calls = 0

    async def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 12:
            reached.set()
            await asyncio.Event().wait()
        raise RuntimeError('permanent provider failure')

    monkeypatch.setattr(module, 'stream_reply', fail)
    task = asyncio.create_task(run_experiment(config, on_delta=None))
    try:
        await asyncio.wait_for(reached.wait(), 5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert calls == 12
    assert not (config.attempt_dir(0) / 'metadata.json').exists()
    assert not config.result_file.exists()


async def test_cancellation_closes_t_and_keeps_u_artifacts(config, botbox_script, monkeypatch):
    botbox_script.advice.append('double it')
    started = asyncio.Event()

    async def block(self, text):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', block)
    task = asyncio.create_task(run_experiment(config, on_delta=None))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
    assert not config.result_file.exists()
    assert botbox_script.sessions and all(session.closed for session in botbox_script.sessions)
    assert any(m.get('content') == 'double it' for m in transcript(config))


async def test_cancellation_reaps_evaluator_before_cleanup(config, botbox_script):
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
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert not config.result_file.exists()
    assert all(session.closed for session in botbox_script.sessions)
    assert any(m.get('content') == 'double it' for m in transcript(config))


@pytest.mark.parametrize('failure', ['infrastructure', 'disk failure'])
async def test_botbox_failure_is_not_generation_completion(config, botbox_script, monkeypatch, failure):
    module = importlib.import_module('surprisals_experiment.sdk.utils.botbox_run')
    original = module.Botbox
    calls = 0

    class BrokenOnce(original):
        async def run(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                if failure == 'disk failure':
                    raise OSError('disk failure')
                return RunResult(exit_code=-1)
            assert not (config.t_dir(0, 0) / 'run.json').exists()
            return await super().run(*args, **kwargs)

    monkeypatch.setattr(module, 'Botbox', BrokenOnce)
    botbox_script.advice.append('Use a loop')
    botbox_script.solutions.append(PASS)
    assert await run_experiment(config, on_delta=None)
    assert calls == 2
    assert failure in (config.attempt_dir(0) / 'error.txt').read_text()
    assert json.loads((config.t_dir(0, 0) / 'run.json').read_text())['exit_code'] == 0
