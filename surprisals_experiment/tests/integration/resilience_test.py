"""Observed provider failures, bounded retries, and interrupted-run diagnostics."""

import json

import httpx2
import pytest
from state_machine.testing import Done, State
from t_timeout_test import advised, attempt, evaluated, opened, solved, t_state, u_state
from u_flush_test import PASS, QUESTION, appended, chat, flush, outcome, played
from utils.world import T, U, t_sent

from surprisals_experiment.config import Config
from surprisals_experiment.retry_policy.constants import DELAYS

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
    async with execute_run_experiment(config, world, u_layout=True):
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


async def test_output_limit_fails_the_turn_and_the_next_turn_sees_none_of_it(config, execute_run_experiment):
    config.max_u_turns = 2
    advice = 'Use a loop'
    best = flush(1, advice, length=10)
    second = [{'role': 'user', 'content': best}, {'role': 'assistant', 'content': advice},
              {'role': 'user', 'content': appended(PASS)}]
    failed_turn = [{'role': 'system', 'content': ...}, {'role': 'user', 'content': QUESTION, '_reset': True},
                   PARTIAL | {'reasoning': 'Cut off'}, {'role': 'system', 'content': ...},
                   {'role': 'user', 'content': QUESTION, '_reset': True}]
    asked = [chat(0, (QUESTION, None))['u/transcripts/messages.jsonl'][0], *failed_turn]
    answer = chat(0, (QUESTION, advice))['u/transcripts/messages.jsonl'][-1]
    world = [
        State(U('partial', thinking='Cut off', finish='length', usage=USAGE),
              sent=u_state(config, 0, 0, QUESTION, advice, {}, u_layout=True).sent,
              logs=[(f'{TURN}/u', 'thinking', 'Cut off'), (f'{TURN}/u', 'text', 'partial')],
              files={'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        # Turn 1 is sent only its system prompt and the question: no partial reasoning or content.
        u_state(config, 0, 1, QUESTION, advice, {
            f'{TURN}/metadata.json': {
                'advice': None, 'error': 'U hit its output token limit (20 completion tokens, 19 reasoning tokens)'},
            'u/transcripts/messages.jsonl': asked, 'u/transcripts/usage.jsonl': [OK | {'usage': USAGE}]}, u_layout=True),
        t_state(0, 1, 0, 0, advice, {'u/transcripts/messages.jsonl': [*asked, answer],
                                     'u/transcripts/usage.jsonl': [OK | {'usage': USAGE}, OK], **advised(0, 1, advice, 10)}),
        u_state(config, 1, 0, best, advice, {**evaluated(attempt(0, 1, 0)), **opened(1), **chat(1, (best, None))},
                previous=10, u_layout=True),
        t_state(1, 0, 0, 0, advice, {**chat(1, (best, advice)), **advised(1, 0, advice)}),
        u_state(config, 1, 1, second, advice, {**evaluated(attempt(1, 0, 0)), **chat(1, (best, advice), (second, None))},
                previous=10, u_layout=True),
        t_state(1, 1, 0, 0, advice, {**chat(1, (best, advice), (second, advice)), **advised(1, 1, advice)}),
        Done(outcome=config.output / attempt(0, 1, 0) / 'src',
             files={**evaluated(attempt(1, 1, 0)), **solved(config, attempt(0, 1, 0), 3)}),
    ]
    async with execute_run_experiment(config, world, u_layout=True):
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
    for retry in range(9):
        world.append(State(t, sent=t_sent(f'{TURN}/ts/0/attempts/{retry}', 'Use a loop'),
                           logs=[(f'{TURN}/ts/0', 'retry', f'T {retry}/8 in {DELAYS[retry - 1]}s: {failure}\n')]
                           if retry else [],
                           files=generation(retry - 1) if retry else pending))
    exhausted = f'T sample failed: {failure}; 8 retries exhausted'
    world.append(Done(outcome=RuntimeError(exhausted),
                      files={**generation(8), f'{TURN}/error.txt': Traceback(exhausted)}))
    async with execute_run_experiment(config, world):
        pass


async def test_fatal_error_restarts_the_run_after_60_seconds(config, execute_run_experiment):
    config = Config(**config.model_dump() | {'infra_retries': 3})
    world, pending = played([[(QUESTION, 'Use a loop', [])]], {'Use a loop': {'score': 10}}, config=config)
    for number in range(9):
        world.append(State(T(error=OSError('disk failure')), sent=t_sent(f'{TURN}/ts/0/attempts/{number}', 'Use a loop'),
                           logs=[(f'{TURN}/ts/0', 'retry', f'T {number}/8 in {DELAYS[number - 1]}s: disk failure\n')]
                           if number else [],
                           files={} if number else pending))
    exhausted = 'T sample failed: disk failure; 8 retries exhausted'
    restarted = t_state(0, 0, 0, 9, 'Use a loop', {f'{TURN}/error.txt': Traceback(exhausted)})
    restarted.logs = [('run', 'retry', f'Run 1/3 in 60s: {exhausted}\n'), *restarted.logs]
    solved_at, best = attempt(0, 0, 0, 9), flush(0, 'Use a loop', length=10)
    world += [
        restarted,
        u_state(config, 1, 0, best, 'Use a loop', {**evaluated(solved_at), **opened(1)},
                previous=10),
        t_state(1, 0, 0, 0, 'Use a loop', {**advised(1, 0, 'Use a loop')}),
        Done(outcome=config.output / solved_at / 'src',
             files={**evaluated(attempt(1, 0, 0)), **solved(config, solved_at, 2)}),
    ]
    async with execute_run_experiment(config, world):
        pass
