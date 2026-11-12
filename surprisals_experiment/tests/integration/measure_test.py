"""Measurement, feedback and scorer recovery through the real HTTP client."""

import math
from hashlib import sha256

import httpx2
import pytest
from openai import BadRequestError
from state_machine.testing import REMOVED
from utils.non_u_layout import Done, State
from surprisals_experiment.config import Config

from surprisals_experiment.retry_policy.constants import DELAYS

from utils.world import U, Score, T, t_sent

PASS = "print(int(input()) * 2)"
QUESTION = 'Read an integer and print its double.'
PASSED = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
    {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
]}
FAILED = {'duration_seconds': 0.0, 'passed': 0, 'failed': 2, 'total': 2, 'all_passed': False, 'cases': [
    {'index': 0, 'passed': False, 'status': 'wrong_answer', 'stdout': '0\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': False, 'status': 'wrong_answer', 'stdout': '0\n', 'stderr': '', 'exit_code': 0},
]}


def turn(window, index):
    return f'windows/{window}/forks/0/turns/{index}'


def advice_path(text):
    return f'advices/{sha256(text.encode()).hexdigest()}'


def flush(index, advice, *, length=None, bits=None):
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>{index}</index>\n'
            + (f'<length>{length} characters</length>\n' if length else '')
            + f'<advice>\n{advice}\n</advice>\n'
            + (f'<bits>\n{bits}\n</bits>\n' if bits else '')
            + f'<code>\n<T-0>\n<file path="main.py">\n{PASS}\n</file>\n<results>2/2 test cases passed</results>\n</T-0>\n</code>\n</attempt>')


def appended(code):
    return (f'<code>\n<T-0>\n<file path="main.py">\n{code}\n</file>\n'
            f'<results>{2 * (code == PASS)}/2 test cases passed</results>\n</T-0>\n</code>')


def chat(*args):
    """Conversation artifacts are checked by the U owner tests."""
    return {}


def opened(window):
    return {f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}


def scored(advice, score):
    return {f'{advice_path(advice)}/advice.txt': advice, f'{advice_path(advice)}/advice.json': score}


def priced(advice, score):
    return {f'{advice_path(advice)}/advice.json': score}


def advised(path, advice):
    return {f'{path}/metadata.json': {'advice': advice_path(advice)}, f'{path}/u/advice.txt': advice}


def unscored(path, advice):
    """What a turn has written when the scorer is asked to price its advice."""
    return {**advised(path, advice), **scored(advice, {})}


def results(path, tests=PASSED):
    return {f'{path}/ts/0/attempts/0/generation.json': {'exit_code': 0}, f'{path}/ts/0/attempts/0/tests.json': tests}


def u_state(config, path, turns, advice, files, previous=None):
    return State(U(advice, thinking='Think.'),
                 sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                       'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
                       'messages': ...},
                 logs=[(f'{path}/u', 'thinking', 'Think.'), (f'{path}/u', 'text', advice)], files=files)


def score_state(advice, files, *, bits=None, logs=(), **error):
    return State(Score(bits, **error), sent=advice, logs=logs, files=files)


def t_state(path, advice, code, files):
    stdout = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write main.py."}}\n'
              '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')
    return State(T({'main.py': code}, thinking='Write main.py.', text='Done.'), sent=t_sent(f'{path}/ts/0/attempts/0', advice),
                 logs=[(f'{path}/ts/0', 'thinking', 'Write main.py.'), (f'{path}/ts/0', 'text', 'Done.')],
                 files={f'{path}/ts/0/attempts/0/stdout.txt': stdout, f'{path}/ts/0/attempts/0/src/main.py': code, **files})


def result(config, solution, attempts, **scoring):
    return {'result.json': {'success': True, 'attempts': attempts, 'solution': str(config.output / solution / 'ts/0/attempts/0/src'),
                            **scoring}}


@pytest.fixture
def scoring_config(config):
    return Config(
        **(
            config.model_dump()
            | {
                "cap_strategy": "surprisal",
                "scorer_base_url": "http://scorer/v1",
            }
        )
    )


SCORING = {'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1', 'scorer_model': 'openai/gpt-oss-120b'}


async def test_character_metadata_has_no_tokens(config, execute_run_experiment):
    first, second = turn(0, 0), turn(1, 0)
    best = flush(0, 'Use a loop', length=10)
    world = [
        u_state(config, first, QUESTION, 'Use a loop', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t_state(first, 'Use a loop', PASS, {**chat(0, (QUESTION, 'Use a loop')), **advised(first, 'Use a loop'),
                                            **scored('Use a loop', {'score': 10})}),
        u_state(config, second, best, 'Use a loop', {**results(first), **opened(1), **chat(1, (best, None))}, previous=10),
        t_state(second, 'Use a loop', PASS, {**chat(1, (best, 'Use a loop')), **advised(second, 'Use a loop')}),
        Done(outcome=config.output / first / 'ts/0/attempts/0/src', files={**results(second), **result(config, first, 2)}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_bits_drive_improvement_feedback_and_result(scoring_config, execute_run_experiment):
    config = scoring_config
    config.max_u_turns = 3
    pairs = [
        [("tiny", 10.5)],
        [("much longer", 3.0), (" but fewer bits", 5.25)],
        [("equal bits", 8.25)],
    ]
    tiny, longer, equal = ("".join(token for token, _ in reply) for reply in pairs)
    first = [turn(0, index) for index in range(3)]
    second = [turn(1, index) for index in range(3)]
    best = flush(1, longer, bits='much longer<3.0> but fewer bits<5.2>')
    window = [(QUESTION, tiny), (None, longer), (None, equal)]
    later = [(best, longer), (None, longer), (None, longer)]
    world = [
        u_state(config, first[0], QUESTION, tiny, {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state(tiny, {**chat(0, *window[:1]), **unscored(first[0], tiny)}, bits=pairs[0]),
        t_state(first[0], tiny, PASS, priced(tiny, {'score': 10.5, 'tokens': [['tiny', 10.5]]})),
        u_state(config, first[1], [*window[:1], (None, None)], longer, {**results(first[0]), **chat(0, *window[:1], (None, None))}),
        score_state(longer, {**chat(0, *window[:2]), **unscored(first[1], longer)}, bits=pairs[1]),
        t_state(first[1], longer, PASS, priced(longer, {
            'score': 8.25, 'tokens': [['much longer', 3.0], [' but fewer bits', 5.25]]})),
        u_state(config, first[2], [*window[:2], (None, None)], equal, {**results(first[1]), **chat(0, *window[:2], (None, None))}),
        score_state(equal, {**chat(0, *window), **unscored(first[2], equal)}, bits=pairs[2]),
        t_state(first[2], equal, PASS, priced(equal, {'score': 8.25, 'tokens': [['equal bits', 8.25]]})),
        u_state(config, second[0], best, longer, {**results(first[2]), **opened(1), **chat(1, (best, None))}, previous=8.25),
        t_state(second[0], longer, PASS, {**chat(1, *later[:1]), **advised(second[0], longer)}),
        u_state(config, second[1], [*later[:1], (None, None)], longer, {**results(second[0]), **chat(1, *later[:1], (None, None))}, previous=8.25),
        t_state(second[1], longer, PASS, {**chat(1, *later[:2]), **advised(second[1], longer)}),
        u_state(config, second[2], [*later[:2], (None, None)], longer, {**results(second[1]), **chat(1, *later[:2], (None, None))}, previous=8.25),
        t_state(second[2], longer, PASS, {**chat(1, *later), **advised(second[2], longer)}),
        Done(outcome=config.output / first[1] / 'ts/0/attempts/0/src', files={**results(second[2]), **result(
            config, first[1], 6, best_measurement=8.25, **SCORING)}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_failed_lower_bits_do_not_replace_success(scoring_config, execute_run_experiment):
    config = scoring_config
    config.max_u_turns = 2
    first = [turn(0, index) for index in range(2)]
    second = [turn(1, index) for index in range(2)]
    best = flush(0, 'good', bits='good<10.0>')
    world = [
        u_state(config, first[0], QUESTION, 'good', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state('good', {**chat(0, (QUESTION, 'good')), **unscored(first[0], 'good')}, bits=[('good', 10.0)]),
        t_state(first[0], 'good', PASS, priced('good', {'score': 10.0, 'tokens': [['good', 10.0]]})),
        u_state(config, first[1], [(QUESTION, 'good'), (None, None)], 'bad', {**results(first[0]), **chat(0, (QUESTION, 'good'), (None, None))}),
        score_state('bad', {**chat(0, (QUESTION, 'good'), (None, 'bad')), **unscored(first[1], 'bad')},
                    bits=[('bad', 1.0)]),
        t_state(first[1], 'bad', 'print(0)', priced('bad', {'score': 1.0, 'tokens': [['bad', 1.0]]})),
        u_state(config, second[0], best, 'good', {**results(first[1], FAILED), **opened(1), **chat(1, (best, None))}, previous=10.0),
        t_state(second[0], 'good', PASS, {**chat(1, (best, 'good')), **advised(second[0], 'good')}),
        u_state(config, second[1], [(best, 'good'), (None, None)], 'good', {**results(second[0]), **chat(1, (best, 'good'), (None, None))}, previous=10.0),
        t_state(second[1], 'good', PASS, {**chat(1, (best, 'good'), (None, 'good')), **advised(second[1], 'good')}),
        Done(outcome=config.output / first[0] / 'ts/0/attempts/0/src', files={**results(second[1]), **result(
            config, first[0], 4, best_measurement=10.0, **SCORING)}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_scorer_failure_retries_with_advice_saved(scoring_config, execute_run_experiment):
    config = scoring_config
    first, second = turn(0, 0), turn(1, 0)
    best = flush(0, 'Use a loop', bits='Use a loop<10.0>')
    retry = "Scorer 1/8 in 10s: Error code: 503 - {'error': {'message': 'scorer failed'}}\n"
    world = [
        u_state(config, first, QUESTION, 'Use a loop', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state('Use a loop', {**chat(0, (QUESTION, 'Use a loop')), **unscored(first, 'Use a loop')},
                    status=503, message='scorer failed'),
        score_state('Use a loop', {}, bits=[('Use a loop', 10.0)], logs=[(f'{first}/u', 'retry', retry)]),
        t_state(first, 'Use a loop', PASS, priced('Use a loop', {'score': 10.0, 'tokens': [['Use a loop', 10.0]]})),
        u_state(config, second, best, 'Use a loop', {**results(first), **opened(1), **chat(1, (best, None))}, previous=10.0),
        t_state(second, 'Use a loop', PASS, {**chat(1, (best, 'Use a loop')), **advised(second, 'Use a loop')}),
        Done(outcome=config.output / first / 'ts/0/attempts/0/src', files={**results(second), **result(
            config, first, 2, best_measurement=10.0, **SCORING)}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_scorer_exhaustion_preserves_advice_and_uses_one_budget(scoring_config, execute_run_experiment):
    first = turn(0, 0)
    failure = "Error code: 503 - {'error': {'message': 'scorer failed'}}"
    waits = [10, 20, 30, 60, 180, 300, 1200, 1800]
    world = [
        u_state(scoring_config, first, QUESTION, 'preserve me', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state('preserve me', {**chat(0, (QUESTION, 'preserve me')), **unscored(first, 'preserve me')},
                    status=503, message='scorer failed'),
        *[score_state('preserve me', {}, status=503, message='scorer failed',
                      logs=[(f'{first}/u', 'retry', f'Scorer {attempt}/8 in {wait}s: {failure}\n')])
          for attempt, wait in enumerate(waits, 1)],
        Done(outcome=RuntimeError(f"Scorer request failed: {failure}; 8 retries exhausted")),
    ]
    async with execute_run_experiment(scoring_config, world):
        pass


async def test_identical_advice_cannot_improve_from_score_jitter(scoring_config, execute_run_experiment):
    config = scoring_config
    config.max_u_turns = 2
    same = 'same advice'
    first = [turn(0, index) for index in range(2)]
    second = [turn(1, index) for index in range(2)]
    best = flush(0, same, bits='same<4.0> advice<6.0>')
    world = [
        u_state(config, first[0], QUESTION, same, {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state(same, {**chat(0, (QUESTION, same)), **unscored(first[0], same)},
                    bits=[("same", 4.0), (" advice", 6.0)]),
        t_state(first[0], same, PASS, priced(same, {'score': 10.0, 'tokens': [['same', 4.0], [' advice', 6.0]]})),
        u_state(config, first[1], [(QUESTION, same), (None, None)], same, {**results(first[0]), **chat(0, (QUESTION, same), (None, None))}),
        t_state(first[1], same, PASS, {**chat(0, (QUESTION, same), (None, same)), **advised(first[1], same)}),
        u_state(config, second[0], best, same, {**results(first[1]), **opened(1), **chat(1, (best, None))}, previous=10.0),
        t_state(second[0], same, PASS, {**chat(1, (best, same)), **advised(second[0], same)}),
        u_state(config, second[1], [(best, same), (None, None)], same, {**results(second[0]), **chat(1, (best, same), (None, None))}, previous=10.0),
        t_state(second[1], same, PASS, {**chat(1, (best, same), (None, same)), **advised(second[1], same)}),
        Done(outcome=config.output / first[0] / 'ts/0/attempts/0/src', files={**results(second[1]), **result(
            config, first[0], 4, best_measurement=10.0, **SCORING)}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_scorer_bad_request_stops_run_without_retry(scoring_config, execute_run_experiment):
    first = turn(0, 0)
    error = "Error code: 400 - {'error': {'message': 'invalid model'}}"
    response = httpx2.Response(400, request=httpx2.Request("POST", "http://scorer/v1/completions"))
    rejected = 'preserve rejected advice'
    world = [
        u_state(scoring_config, first, QUESTION, rejected, {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state(rejected, {**chat(0, (QUESTION, rejected)), **unscored(first, rejected)},
                    status=400, message='invalid model'),
        Done(outcome=BadRequestError(error, response=response, body=None)),
    ]
    async with execute_run_experiment(scoring_config, world):
        pass


OVERFLOW = "maximum context length is 8192 tokens"


def retried_chat(*args):
    """Conversation retries are checked by the U owner tests."""
    return {}


def rejected(path, index):
    advice = f'too long {index}'
    return {f'{path}/metadata.json': REMOVED, f'{path}/u/advice.txt': REMOVED, f'{path}/u/rejected/{index}.txt': advice}


async def test_advice_over_scorer_context_reruns_u(scoring_config, execute_run_experiment):
    config = scoring_config
    first, second = turn(0, 0), turn(1, 0)
    best = flush(0, 'Use a loop', bits='Use a loop<10.0>')
    world = [
        u_state(config, first, QUESTION, 'too long 0', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state('too long 0', {**chat(0, (QUESTION, 'too long 0')), **unscored(first, 'too long 0')},
                    status=400, message=OVERFLOW),
        u_state(config, first, QUESTION, 'Use a loop', {**retried_chat(1, None), **rejected(first, 0)}),
        score_state('Use a loop', {**retried_chat(1, 'Use a loop'), **unscored(first, 'Use a loop')},
                    bits=[('Use a loop', 10.0)]),
        t_state(first, 'Use a loop', PASS, priced('Use a loop', {'score': 10.0, 'tokens': [['Use a loop', 10.0]]})),
        u_state(config, second, best, 'Use a loop', {**results(first), **opened(1), **chat(1, (best, None))}, previous=10.0),
        t_state(second, 'Use a loop', PASS, {**chat(1, (best, 'Use a loop')), **advised(second, 'Use a loop')}),
        Done(outcome=config.output / first / 'ts/0/attempts/0/src', files={**results(second), **result(
            config, first, 2, best_measurement=10.0, **SCORING)}),
    ]
    async with execute_run_experiment(config, world):
        pass


def overflowing(config):
    """Every advice U writes for turn 0 is over the scorer's context."""
    first = turn(0, 0)
    error = f"Advice exceeded the scorer's context limit: Error code: 400 - {{'error': {{'message': '{OVERFLOW}'}}}}"
    response = httpx2.Response(400, request=httpx2.Request("POST", "http://scorer/v1/completions"))
    world = [
        u_state(config, first, QUESTION, 'too long 0', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state('too long 0', {**chat(0, (QUESTION, 'too long 0')), **unscored(first, 'too long 0')},
                    status=400, message=OVERFLOW),
    ]
    for index in range(1, len(DELAYS) + 1):
        advice = f'too long {index}'
        world += [
            u_state(config, first, QUESTION, advice, {**retried_chat(index, None), **rejected(first, index - 1)}),
            score_state(advice, {**retried_chat(index, advice), **unscored(first, advice)}, status=400, message=OVERFLOW),
        ]
    return world + [Done(outcome=BadRequestError(error, response=response, body=None))]


async def test_advice_over_scorer_context_every_attempt_stops_run(scoring_config, execute_run_experiment):
    world = overflowing(scoring_config)
    async with execute_run_experiment(scoring_config, world):
        pass


async def test_relaunch_after_overflow_keeps_counting_attempts(scoring_config, execute_run_experiment):
    world = overflowing(scoring_config)
    killed = world[:4]
    async with execute_run_experiment(scoring_config, killed) as run:
        await run.reached(killed[-1])
        run.kill()
    relaunched = [score_state('too long 1', {}, status=400, message=OVERFLOW), *world[4:]]
    config = Config(**scoring_config.model_dump())
    async with execute_run_experiment(config, relaunched):
        pass


@pytest.mark.parametrize("bits", [math.nan, math.inf])
async def test_non_finite_score_retries_like_a_scorer_failure(scoring_config, execute_run_experiment, bits):
    config = scoring_config
    first, second = turn(0, 0), turn(1, 0)
    best = flush(0, 'Use a loop', bits='Use a loop<10.0>')
    retry = f"Scorer 1/8 in 10s: Scorer returned non-finite surprisal: [('Use a loop', {bits})]\n"
    world = [
        u_state(config, first, QUESTION, 'Use a loop', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        score_state('Use a loop', {**chat(0, (QUESTION, 'Use a loop')), **unscored(first, 'Use a loop')},
                    bits=[('Use a loop', bits)]),
        score_state('Use a loop', {}, bits=[('Use a loop', 10.0)], logs=[(f'{first}/u', 'retry', retry)]),
        t_state(first, 'Use a loop', PASS, priced('Use a loop', {'score': 10.0, 'tokens': [['Use a loop', 10.0]]})),
        u_state(config, second, best, 'Use a loop', {**results(first), **opened(1), **chat(1, (best, None))}, previous=10.0),
        t_state(second, 'Use a loop', PASS, {**chat(1, (best, 'Use a loop')), **advised(second, 'Use a loop')}),
        Done(outcome=config.output / first / 'ts/0/attempts/0/src', files={**results(second), **result(
            config, first, 2, best_measurement=10.0, **SCORING)}),
    ]
    async with execute_run_experiment(config, world):
        pass
