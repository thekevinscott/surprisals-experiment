"""Observed provider failures, bounded retries, and interrupted-run diagnostics."""

import asyncio
import json
import os
from contextlib import chdir

import httpx2
import pytest

from surprisals_experiment.retry_policy.constants import DELAYS
from run_one_window import run_one_window
from u_flush_test import PASS, QUESTION, chat, flush, outcome, played
from utils.world import U, Done, State, T, t_sent


def transcript(config):
    return [json.loads(line) for line in
            (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]


def length_reply(tokens=None):
    reply = {'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': 'length'}
    if tokens is not None:
        reply['usage'] = {'prompt_tokens': 10, 'completion_tokens': tokens, 'total_tokens': tokens + 10,
                          'completion_tokens_details': {'reasoning_tokens': tokens - 1}}
    return reply


BUILD = {'agent': {'provider': 'openrouter', 'model': 't', 'api_key': 'test-key'}, 'dockerfile': 'docker/Dockerfile.t'}
TURN = 'windows/0/forks/0/turns/0'
OK = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
USAGE = {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30,
         'completion_tokens_details': {'reasoning_tokens': 19}}
PARTIAL = {'role': 'assistant', 'content': 'partial', '_complete': False}
WINDOWS = [[(QUESTION, 'Use a loop', [PASS])], [(flush(0, 'Use a loop', length=10), 'Use a loop', [PASS])]]
CHUNK = {'id': 'u', 'choices': [{'delta': {'content': 'partial', 'role': 'assistant'}, 'index': 0,
                                 'finish_reason': 'error', 'error': {'message': 'upstream failed', 'code': 502}}],
         'created': 1, 'model': 'u', 'object': 'chat.completion.chunk'}


class Traceback(str):
    """Equals a formatted traceback that ends in RuntimeError(self)."""

    def __eq__(self, other):
        return other.startswith('Traceback (most recent call last):\n') and other.endswith(f'RuntimeError: {self}\n')

    __hash__ = str.__hash__


@pytest.mark.parametrize('failure,shown,error,recorded,row', [
    pytest.param(U(thinking='Hmm: what about'), [('thinking', 'Hmm: what about')],
                 'U chat did not produce complete advice (stop)',
                 {'role': 'assistant', 'reasoning': 'Hmm: what about', '_complete': False}, OK,
                 id='thinking-only-stop'),
    pytest.param(U('partial', finish='content_filter'), [('text', 'partial')],
                 'Could not parse response content as the request was rejected by the content filter', PARTIAL, OK,
                 id='content-filter'),
    pytest.param(U(error=httpx2.ConnectError('Connection error')), [], 'Connection error.', None,
                 OK | {'completion_id': None}, id='connection-error'),
    pytest.param(U('partial', finish=None, drop=True), [('text', 'partial')], 'Connection error.', PARTIAL, OK,
                 id='dropped-stream'),
    pytest.param(U('partial', thinking='partial reasoning', finish='error',
                   choice={'error': CHUNK['choices'][0]['error']}),
                 [('thinking', 'partial reasoning'), ('text', 'partial')],
                 f'U chat provider error: {json.dumps(CHUNK)}',
                 PARTIAL | {'reasoning': 'partial reasoning', 'provider_error': CHUNK}, OK, id='provider-error'),
    pytest.param(U('partial', finish='length', usage=USAGE), [('text', 'partial')],
                 'U hit its output token limit (20 completion tokens, 19 reasoning tokens)', PARTIAL,
                 OK | {'usage': USAGE}, id='output-limit'),
])
async def test_failed_reply_retries_original_history(
    config, execute_run_experiment, failure, shown, error, recorded, row,
):
    world, pending = played(WINDOWS, {'Use a loop': {'score': 10}})
    retried, tested = world[0], world[1]
    asked = chat(0, (QUESTION, None))['u/transcripts/messages.jsonl']
    partial = [] if recorded is None else [recorded]
    failed = State(failure, sent=retried.sent, logs=[(f'{TURN}/u', kind, text) for kind, text in shown],
                   files=retried.files)
    retried.logs = [(f'{TURN}/u', 'retry', f'1/8 in 10s: {error}\n'), *retried.logs]
    retried.files = {'u/transcripts/usage.jsonl': [row]}
    if partial:
        retried.files['u/transcripts/messages.jsonl'] = [*asked, *partial]
    answer = chat(0, (QUESTION, 'Use a loop'))['u/transcripts/messages.jsonl'][-1]
    tested.files['u/transcripts/messages.jsonl'] = [*asked, *partial, answer]
    tested.files['u/transcripts/usage.jsonl'] = [row, OK]
    world = [failed, *world, outcome(config, TURN, 2, pending)]
    async with execute_run_experiment(config, world):
        pass


async def test_credential_proxy_startup_retries(config, execute_run_experiment):
    first, second = f'{TURN}/ts/0/attempts/0', f'{TURN}/ts/0/attempts/1'
    world, pending = played(WINDOWS, {'Use a loop': {'score': 10}})
    for state in world:
        state.files = {path.replace(first, second): value for path, value in state.files.items()}
    built = world[1]
    built.sent = t_sent(second, 'Use a loop')
    retried = State(T(build_error=RuntimeError('botbox credential proxy did not start:\n')), sent=BUILD,
                    files={path: value for path, value in built.files.items() if not path.startswith(second)})
    built.files = {path: value for path, value in built.files.items() if path.startswith(second)}
    built.logs = [(f'{TURN}/ts/0', 'retry', 'T 1/8 in 10s: botbox credential proxy did not start:\n\n'), *built.logs]
    solution = config.output / second / 'src'
    world = [world[0], retried, *world[1:], Done(outcome=solution, files={**pending, 'result.json': {
        'success': True, 'attempts': 2, 'solution': str(solution)}})]
    async with execute_run_experiment(config, world):
        pass


@pytest.fixture
def in_problem_dir(config):
    with chdir(config.problem_dir):
        yield


async def test_length_and_http_errors_share_one_budget(
    config, botbox_script, chat_provider, no_retry_wait, in_problem_dir, capsys,
):
    botbox_script.advice.extend([{'status': 503}, length_reply()] * 4 + [length_reply(100)])
    from surprisals_experiment.cli.main import main

    (config.problem_dir / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
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


@pytest.mark.parametrize('t,failure', [
    pytest.param(T(exit_code=-1), 'T infrastructure failed: botbox could not obtain an exit code', id='infrastructure'),
    pytest.param(T(error=OSError('disk failure')), 'disk failure', id='disk-failure'),
])
async def test_botbox_failure_retains_infrastructure_and_traceback_diagnostics(
    config, execute_run_experiment, t, failure,
):
    world, pending = played([[(QUESTION, 'Use a loop', [])]], {'Use a loop': {'score': 10}})
    generation = (lambda attempt: {f'{TURN}/ts/0/attempts/{attempt}/generation.json': {'exit_code': -1}}
                  if t.exit_code == -1 else {})
    for attempt in range(9):
        world.append(State(t, sent=t_sent(f'{TURN}/ts/0/attempts/{attempt}', 'Use a loop'),
                           logs=[(f'{TURN}/ts/0', 'retry', f'T {attempt}/8 in {DELAYS[attempt - 1]}s: {failure}\n')]
                           if attempt else [],
                           files=generation(attempt - 1) if attempt else pending))
    exhausted = f'T sample failed: {failure}; 8 retries exhausted'
    world.append(Done(outcome=RuntimeError(exhausted),
                      files={**generation(8), f'{TURN}/error.txt': Traceback(exhausted)}))
    async with execute_run_experiment(config, world):
        pass
