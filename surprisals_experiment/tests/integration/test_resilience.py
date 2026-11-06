"""Observed provider failures, bounded retries, and interrupted-run diagnostics."""

import asyncio
import json
import os
from unittest.mock import patch

import httpx2
import pytest

from botbox import RunResult

from surprisals_experiment.retry_policy.constants import DELAYS
from run_one_window import run_one_window
from utils.world import U, State, T

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
    assert await run_one_window(config, on_delta=None) == config.t_dir(0, 0) / 'attempts/0/src'
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


async def test_credential_proxy_startup_retries(config, botbox_script, no_retry_wait):
    from surprisals_experiment.sdk.utils.botbox_run.botbox_run import Botbox
    builds = []

    class FailingEntry(Botbox):
        async def build(self):
            builds.append(self)
            if len(builds) == 1:
                raise RuntimeError('botbox credential proxy did not start:\n')
            return await super().build()

    botbox_script.advice.append('Use a loop')
    botbox_script.solutions.append(PASS)
    with patch('surprisals_experiment.sdk.utils.botbox_run.botbox_run.Botbox', FailingEntry):
        assert await run_one_window(config, on_delta=None) == config.t_dir(0, 0) / 'attempts/0/src'
    assert len(builds) == 2
    no_retry_wait.assert_awaited_once_with(10)


async def test_length_and_http_errors_share_one_budget(
    config, botbox_script, chat_provider, no_retry_wait, monkeypatch, capsys,
):
    botbox_script.advice.extend([{'status': 503}, length_reply()] * 4 + [length_reply(100)])
    from surprisals_experiment.cli.main import main

    (config.problem_dir / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
    monkeypatch.chdir(config.problem_dir)
    with pytest.raises(SystemExit) as raised:
        await main(['--window-forks', '1', '--output', str(config.output), '--t-samples', '1',
                    str(config.problem_dir)])
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
    await run_one_window(config, on_delta=None)


async def test_cancellation_closes_t_and_keeps_u_artifacts(config, execute_run_experiment):
    question = 'Read an integer and print its double.'
    advice = 'advices/2aaeab9c9ac9f05b410e758c97bd7357adf65eeb0fbfdef5eb92107315271625'
    asked = [{'role': 'system', 'content': ...}, {'role': 'system', 'content': ...},
             {'role': 'user', 'content': question, '_reset': True}]
    world = [
        State(
            U('double it', thinking='Ask for doubling.'),
            sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                  'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': question}]},
            logs=[
                ('windows/0/forks/0/turns/0/u', 'thinking', 'Ask for doubling.'),
                ('windows/0/forks/0/turns/0/u', 'text', 'double it'),
            ],
            files={
                'settings.json': ...,
                'u/transcripts/messages.jsonl': asked,
                'windows/0/window.json': {},
                'windows/0/forks/0/fork.json': {},
            },
        ),
        State(
            T({'main.py': PASS}, thinking='Write main.py.', text='Done.'),
            sent=('windows/0/forks/0/turns/0/ts/0', 'double it'),
            logs=[
                ('windows/0/forks/0/turns/0/ts/0', 'thinking', 'Write main.py.'),
                ('windows/0/forks/0/turns/0/ts/0', 'text', 'Done.'),
            ],
            files={
                'u/transcripts/messages.jsonl': [*asked, {'role': 'assistant', 'content': 'double it',
                                                          'reasoning': 'Ask for doubling.', '_complete': True}],
                'u/transcripts/usage.jsonl': [{'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u',
                                               'usage': None}],
                f'{advice}/advice.txt': 'double it',
                f'{advice}/advice.json': {'score': 9},
                'windows/0/forks/0/turns/0/metadata.json': {'advice': advice},
                'windows/0/forks/0/turns/0/u/advice.txt': 'double it',
                'windows/0/forks/0/turns/0/ts/0/stdout.txt': ...,
                'windows/0/forks/0/turns/0/ts/0/src/main.py': PASS,
            },
        ),
    ]
    async with execute_run_experiment(config, world) as run:
        await run.reached(world[1])
        run.kill()
    assert not config.result_file.exists()


async def test_cancellation_reaps_evaluator_before_cleanup(config, botbox_script):
    botbox_script.advice.append('double it')
    botbox_script.solutions.append(
        "import os, time\nfrom pathlib import Path\n"
        "Path('pid').write_text(str(os.getpid()))\ntime.sleep(60)\n"
    )
    task = asyncio.create_task(run_one_window(config, on_delta=None))
    pid_file = config.t_dir(0, 0) / 'attempts/0/src' / 'pid'
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
    config, botbox_script, no_retry_wait,
):
    from surprisals_experiment.sdk.utils.botbox_run.botbox_run import Botbox
    root = config.output
    for failure in ('infrastructure', 'disk failure'):
        class BrokenBotbox(Botbox):
            async def run(self, *args, **kwargs):
                if failure == 'disk failure':
                    raise OSError('disk failure')
                return RunResult(exit_code=-1)

        config.output = root / failure.replace(' ', '-')
        botbox_script.advice.append('Use a loop')
        with patch('surprisals_experiment.sdk.utils.botbox_run.botbox_run.Botbox', BrokenBotbox):
            with pytest.raises(RuntimeError, match=failure):
                await run_one_window(config, on_delta=None)
        diagnostics = (config.attempt_dir(0) / 'error.txt').read_text()
        assert failure in diagnostics
        assert 'Traceback' in diagnostics
        assert not (config.t_dir(0, 0) / 'tests.json').exists()
        if failure == 'infrastructure':
            assert json.loads((config.t_dir(0, 0) / 'attempts/0/generation.json').read_text())['exit_code'] == -1
