"""Observed provider failures, bounded retries, and interrupted-run diagnostics."""

import json

import httpx2
import pytest
from state_machine.testing import Done, State
from t_timeout_test import advised, attempt, evaluated, opened, solved, t_state, u_state
from u_flush_test import PASS, QUESTION, appended, chat, flush, outcome, played
from utils.world import u_followup, u_opening, T, U, t_sent, u_user

from surprisals_experiment.config import Config
from surprisals_experiment.retry_policy.constants import DELAYS

BUILD = {'agent': {'provider': 'openrouter', 'model': 't', 'api_key': 'test-key'}, 'dockerfile': 'docker/Dockerfile.t'}
TURN = 'windows/0/forks/0/turns/0'
USAGE = {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30,
         'completion_tokens_details': {'reasoning_tokens': 19}}
WINDOWS = [[(QUESTION, 'Use a loop', [PASS])], [(flush(0, 'Use a loop', length=10), 'Use a loop', [PASS])]]
CHUNK = {'id': 'u', 'choices': [{'delta': {'content': 'partial', 'role': 'assistant'}, 'index': 0,
                                 'finish_reason': 'error', 'error': {'message': 'upstream failed', 'code': 502}}],
         'created': 1, 'model': 'u', 'object': 'chat.completion.chunk'}


class Traceback(str):
    """Equals a formatted traceback that ends in RuntimeError(self)."""

    def __eq__(self, other):
        return other.startswith('Traceback (most recent call last):\n') and other.endswith(f'RuntimeError: {self}\n')

    __hash__ = str.__hash__


@pytest.mark.parametrize('failure,shown,error', [
    pytest.param(U(thinking='Hmm: what about'), [('thinking', 'Hmm: what about')],
                 'U chat did not produce complete advice (stop)',
                 id='thinking-only-stop'),
    pytest.param(U('partial', finish='content_filter'), [('text', 'partial')],
                 'Could not parse response content as the request was rejected by the content filter',
                 id='content-filter'),
    pytest.param(U(error=httpx2.ConnectError('Connection error')), [], 'Connection error.', id='connection-error'),
    pytest.param(U('partial', finish=None, drop=True), [('text', 'partial')], 'Connection error.',
                 id='dropped-stream'),
    pytest.param(U(thinking='discard this interrupted reasoning', finish=None, drop=True),
                 [('thinking', 'discard this interrupted reasoning')], 'Connection error.',
                 id='dropped-reasoning-stream'),
    pytest.param(U('partial', thinking='partial reasoning', finish='error',
                   choice={'error': CHUNK['choices'][0]['error']}),
                 [('thinking', 'partial reasoning'), ('text', 'partial')],
                 f'U chat provider error: {json.dumps(CHUNK)}', id='provider-error'),
])
async def test_failed_reply_retries_original_history(
    config, execute_run_experiment, failure, shown, error,
):
    config.max_u_turns = 2
    windows = [[*window, (None, 'Use a loop', [PASS])] for window in WINDOWS]
    world, pending = played(windows, {'Use a loop': {'score': 10}}, config=config)
    retried = world[0]
    failed = State(failure, sent=retried.sent, logs=[(f'{TURN}/u', kind, text) for kind, text in shown],
                   files=retried.files)
    retried.logs = [(f'{TURN}/u', 'retry', f'1/8 in 10s: {error}\n'), *retried.logs]
    retried.files = {}
    # Failed replies never change the transcript; every retry sends the same exact history.
    world = [failed, *world, outcome(config, TURN, 4, pending)]
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


async def test_output_limit_next_turn_reports_failure_without_failed_content(config, execute_run_experiment):
    config.max_u_turns = 2
    advice = 'Use a loop'
    best = flush(1, advice, length=10)
    second = [*u_opening(config, best, 10), {'role': 'assistant', 'content': advice},
              {'role': 'user', 'content': '<advice_length>10 characters</advice_length>'},
              *u_followup(config, 2, appended(PASS), 10)]
    failure = ('Your previous reply failed: U hit its output token limit '
               '(20 completion tokens, 19 reasoning tokens). No advice was produced.')
    asked = [*chat(0, (QUESTION, None), config=config)['windows/0/forks/0/u/transcript.jsonl'],
             {'role': 'user', 'content': failure},
             {'role': 'user', 'content': u_user(config, 2), '_attempt': 1}]
    answer = chat(0, (QUESTION, advice), config=config)['windows/0/forks/0/u/transcript.jsonl'][-2:]
    world = [
        State(U('partial', thinking='Cut off', finish='length', usage=USAGE),
              sent=u_state(config, 0, 0, QUESTION, advice, {}, u_layout=True).sent,
              logs=[(f'{TURN}/u', 'thinking', 'Cut off'), (f'{TURN}/u', 'text', 'partial')],
              files={'settings.json': ..., **opened(0), **chat(0, (QUESTION, None), config=config)}),
        # The next turn reports only the recorded failure, before the separate turn message.
        u_state(config, 0, 1, [*u_opening(config, QUESTION),
                               *u_followup(config, 2, failure)], advice, {
            f'{TURN}/metadata.json': {
                'advice': None, 'error': 'U hit its output token limit (20 completion tokens, 19 reasoning tokens)'},
            'windows/0/forks/0/u/transcript.jsonl': asked}, u_layout=True),
        t_state(0, 1, 0, 0, advice, {'windows/0/forks/0/u/transcript.jsonl': [*asked, *answer],
                                     **advised(0, 1, advice, 10)}),
        u_state(config, 1, 0, best, advice, {**evaluated(attempt(0, 1, 0)), **opened(1), **chat(1, (best, None), config=config, best=10)},
                previous=10, u_layout=True),
        t_state(1, 0, 0, 0, advice, {**chat(1, (best, advice), config=config, best=10), **advised(1, 0, advice)}),
        u_state(config, 1, 1, second, advice, {**evaluated(attempt(1, 0, 0)), **chat(1, (best, advice), (second, None), config=config, best=10)},
                previous=10, u_layout=True),
        t_state(1, 1, 0, 0, advice, {**chat(1, (best, advice), (second, advice), config=config, best=10), **advised(1, 1, advice)}),
        Done(outcome=config.output / attempt(0, 1, 0) / 'src',
             files={**evaluated(attempt(1, 1, 0)), **solved(config, attempt(0, 1, 0), 3)}),
    ]
    world[1].logs.insert(0, (f'{TURN}/u', 'usage', json.dumps({
        'completion_tokens': 20, 'prompt_tokens': 10, 'total_tokens': 30,
        'completion_tokens_details': {'reasoning_tokens': 19},
    })))
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
