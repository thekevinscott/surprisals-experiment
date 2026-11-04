"""Observed provider failures, bounded retries, and interrupted-run diagnostics."""

import asyncio
import importlib
import json
import os

import httpx2
import pytest
from botbox import RunResult

from conftest import FakeSession
from surprisals_experiment.retry_policy import DELAYS
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_chat import open_u_chat

PASS = 'print(int(input()) * 2)'
PROVIDER_ERROR = {
    'deltas': [{'role': 'assistant', 'content': 'partial', 'reasoning': 'partial reasoning'}],
    'finish': 'error', 'finish_choice': {'error': {'message': 'upstream failed', 'code': 502}},
}


def transcript(config):
    return [json.loads(line) for line in
            (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]


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
async def test_failed_reply_retries_original_history(
    config, botbox_script, chat_provider, no_retry_wait, failure,
):
    botbox_script.advice.extend([failure, 'Use a loop'])
    botbox_script.solutions.append(PASS)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(chat_provider) == 2
    assert chat_provider[0]['messages'] == chat_provider[1]['messages']
    no_retry_wait.assert_awaited_once_with(10)
    messages = transcript(config)
    if isinstance(failure, dict):
        partial = next(m for m in messages if m.get('content') == 'partial' or
                       m.get('reasoning') == 'Hmm: what about')
        if failure.get('finish') == 'error':
            assert partial['reasoning'] == 'partial reasoning'
            assert partial['provider_error']['choices'][0]['error'] == failure['finish_choice']['error']
    assert any(m.get('content') == 'Use a loop' for m in messages)


async def test_credential_proxy_startup_retries(config, botbox_script, monkeypatch, no_retry_wait):
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
    no_retry_wait.assert_awaited_once_with(10)


async def test_provider_error_exhaustion_preserves_partial_evidence(
    config, botbox_script, chat_provider, no_retry_wait,
):
    botbox_script.advice.extend([PROVIDER_ERROR] * (len(DELAYS) + 1))
    with pytest.raises(RuntimeError, match=r'U chat request failed:.*8 retries exhausted') as raised:
        async with open_u_chat(config) as session:
            await session.prompt('question')
    assert 'U chat provider error' in str(raised.value)
    assert 'upstream failed' in str(raised.value)
    assert len(chat_provider) == len(DELAYS) + 1
    assert all(request['messages'] == chat_provider[0]['messages'] for request in chat_provider)
    assert [m['content'] for m in transcript(config) if m['role'] == 'assistant'] == ['partial'] * 9
    assert session.messages[-1]['content'] == 'partial'
    assert no_retry_wait.await_count == len(DELAYS)


async def test_length_and_http_errors_share_one_budget(
    config, botbox_script, chat_provider, no_retry_wait, monkeypatch, capsys,
):
    botbox_script.advice.extend([{'status': 503}, length_reply()] * 4 + [length_reply(100)])
    from surprisals_experiment.cli.main import main

    (config.problem_dir / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
    monkeypatch.chdir(config.problem_dir)
    with pytest.raises(SystemExit) as raised:
        await main(['--output', str(config.output), '--t-samples', '1',
                    'problem', str(config.problem_dir)])
    assert raised.value.code == 2
    error = capsys.readouterr().err.splitlines()[-1]
    assert 'U hit its output token limit' in error
    assert '100 completion tokens' in error and '99 reasoning tokens' in error
    assert '8 retries exhausted' in error
    assert len(chat_provider) == 9
    assert all(request['messages'] == chat_provider[0]['messages'] for request in chat_provider)
    assert [m['content'] for m in transcript(config) if m['role'] == 'assistant'] == ['partial'] * 5
    assert no_retry_wait.await_count == len(DELAYS)


@pytest.mark.xfail(strict=True, reason='undecided: the run still exits once retries run out')
async def test_run_continues_after_u_output_limit_exhaustion(config, botbox_script, no_retry_wait):
    config.max_u_turns = 2
    botbox_script.advice.extend([length_reply()] * 9 + ['Use a loop'])
    botbox_script.solutions.append(PASS)
    await run_experiment(config, on_delta=None)


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


async def test_botbox_failure_retains_infrastructure_and_traceback_diagnostics(
    config, botbox_script, monkeypatch, no_retry_wait,
):
    module = importlib.import_module('surprisals_experiment.sdk.utils.botbox_run')
    original = module.Botbox
    root = config.output
    for failure in ('infrastructure', 'disk failure'):
        class BrokenBotbox(original):
            async def run(self, *args, **kwargs):
                if failure == 'disk failure':
                    raise OSError('disk failure')
                return RunResult(exit_code=-1)

        monkeypatch.setattr(module, 'Botbox', BrokenBotbox)
        config.output = root / failure.replace(' ', '-')
        botbox_script.advice.append('Use a loop')
        with pytest.raises(RuntimeError, match=failure):
            await run_experiment(config, on_delta=None)
        diagnostics = (config.attempt_dir(0) / 'error.txt').read_text()
        assert failure in diagnostics
        assert 'Traceback' in diagnostics
        assert not (config.t_dir(0, 0) / 'tests.json').exists()
        if failure == 'infrastructure':
            assert json.loads((config.t_dir(0, 0) / 'generation.json').read_text())['exit_code'] == -1
