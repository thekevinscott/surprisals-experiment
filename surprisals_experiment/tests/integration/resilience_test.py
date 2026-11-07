"""Observed provider failures, bounded retries, and interrupted-run diagnostics."""

import json
from contextlib import chdir

import httpx2
import pytest

from state_machine.testing import Done, State
from surprisals_experiment.config import U_MODEL
from surprisals_experiment.retry_policy.constants import DELAYS
from t_timeout_test import advised, attempt, evaluated, opened, solved, t_state, u_state
from u_flush_test import PASS, QUESTION, chat, flush, outcome, played
from utils.world import U, T, t_sent, u_system


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
    world, pending = played(WINDOWS, {'Use a loop': {'score': 10}}, config=config)
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
    world, pending = played(WINDOWS, {'Use a loop': {'score': 10}}, config=config)
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


async def exit_code(run):
    try:
        await run
    except SystemExit as exit:
        return exit.code


@pytest.fixture
def in_problem_dir(config):
    with chdir(config.problem_dir):
        yield


async def test_length_and_http_errors_share_one_budget(config, in_problem_dir, capsys, execute_run_experiment):
    from surprisals_experiment.cli.main import main

    (config.problem_dir / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
    limit = {'prompt_tokens': 10, 'completion_tokens': 100, 'total_tokens': 110,
             'completion_tokens_details': {'reasoning_tokens': 99}}
    replies = [U(status=503), U('partial', finish='length')] * 4 + [U('partial', finish='length', usage=limit)]
    sent = {'model': U_MODEL, 'stream': True, 'reasoning': {'effort': 'high'},
            'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
            'messages': [{'role': 'system', 'content': u_system(config.model_copy(update={'max_u_turns': None}), 1)},
                         {'role': 'user', 'content': QUESTION}]}
    messages = chat(0, (QUESTION, None))['u/transcripts/messages.jsonl']
    usage = []
    world = []
    files = {'settings.json': ..., 'windows/0/window.json': {}, 'windows/0/forks/0/fork.json': {},
             'u/transcripts/messages.jsonl': messages}
    for reply in replies:
        world.append(State(reply, sent=sent, files=files))
        usage = [*usage, OK | ({'completion_id': None} if reply.status != 200 else {'usage': reply.usage})]
        files = {'u/transcripts/usage.jsonl': usage}
        if reply.status == 200:
            messages = [*messages, PARTIAL]
            files['u/transcripts/messages.jsonl'] = messages
    world.append(Done(outcome=2, files=files))
    async with execute_run_experiment(config, world, run=exit_code(main(
            ['--window-forks', '1', '--output', str(config.output), '--t-samples', '1', str(config.problem_dir)]))):
        pass
    error = capsys.readouterr().err.splitlines()[-1]
    assert 'U hit its output token limit' in error
    assert '100 completion tokens' in error and '99 reasoning tokens' in error
    assert '8 retries exhausted' in error


async def test_output_limit_fails_the_turn_and_runs_the_next_one(config, execute_run_experiment):
    config.max_u_turns = 2
    advice = 'Use a loop'
    best = flush(1, advice, length=10)
    failed_turn = [{'role': 'system', 'content': ...}, {'role': 'user', 'content': QUESTION, '_reset': True},
                   PARTIAL, {'role': 'system', 'content': ...}, {'role': 'user', 'content': QUESTION, '_reset': True}]
    asked = [chat(0, (QUESTION, None))['u/transcripts/messages.jsonl'][0], *failed_turn]
    answer = chat(0, (QUESTION, advice))['u/transcripts/messages.jsonl'][-1]
    world = [
        State(U('partial', finish='length'), sent=u_state(config, 0, 0, QUESTION, advice, {}).sent,
              logs=[(f'{TURN}/u', 'text', 'partial')],
              files={'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        u_state(config, 0, 1, QUESTION, advice, {
            f'{TURN}/metadata.json': {'advice': None, 'error': 'U hit its output token limit'},
            'u/transcripts/messages.jsonl': asked, 'u/transcripts/usage.jsonl': [OK]}),
        t_state(0, 1, 0, 0, advice, {'u/transcripts/messages.jsonl': [*asked, answer],
                                     'u/transcripts/usage.jsonl': [OK, OK], **advised(0, 1, advice, 10)}),
        u_state(config, 1, 0, best, advice, {**evaluated(attempt(0, 1, 0)), **opened(1), **chat(1, (best, None))},
                previous=10),
        t_state(1, 0, 0, 0, advice, {**chat(1, (best, advice)), **advised(1, 0, advice)}),
        u_state(config, 1, 1, best, advice, {**evaluated(attempt(1, 0, 0)), **chat(1, (best, advice), (best, None))},
                previous=10),
        t_state(1, 1, 0, 0, advice, {**chat(1, (best, advice), (best, advice)), **advised(1, 1, advice)}),
        Done(outcome=config.output / attempt(0, 1, 0) / 'src',
             files={**evaluated(attempt(1, 1, 0)), **solved(config, attempt(0, 1, 0), 3)}),
    ]
    async with execute_run_experiment(config, world):
        pass


@pytest.mark.parametrize('t,failure', [
    pytest.param(T(exit_code=-1), 'T infrastructure failed: botbox could not obtain an exit code', id='infrastructure'),
    pytest.param(T(error=OSError('disk failure')), 'disk failure', id='disk-failure'),
])
async def test_botbox_failure_retains_infrastructure_and_traceback_diagnostics(
    config, execute_run_experiment, t, failure,
):
    world, pending = played([[(QUESTION, 'Use a loop', [])]], {'Use a loop': {'score': 10}}, config=config)
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
