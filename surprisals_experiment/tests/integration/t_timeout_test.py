"""Hung T samples retry and real CLI SIGTERM cancels both model phases."""
import asyncio
import signal
from contextlib import chdir
from hashlib import sha256

import pytest
from run_state_machine_test import settings
from state_machine.testing import Done, State
from u_flush_test import (
    PASS,
    QUESTION,
    STDOUT,
    flush,
    outcome,
    played,
    results,
)
from utils.world import T, U, t_sent, u_system, u_user

from surprisals_experiment.cli.main import main
from surprisals_experiment.config import U_MODEL


def u_state(config, window, turn, prompt, advice, files, previous=None, *, u_layout=False):
    """`prompt` is raw opening text, or a conversation with turn-prefixed user messages."""
    path = f'windows/{window}/forks/0/turns/{turn}'
    return State(U(advice, thinking='Think.'),
                 sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                       'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
                       **({'messages': [{'role': 'system', 'content': u_system(config)},
                                        *(prompt if isinstance(prompt, list) else [{'role': 'user', 'content': u_user(config, turn + 1, prompt, previous)}])]}
                          if u_layout else {})},
                 logs=[(f'{path}/u', 'thinking', 'Think.'), (f'{path}/u', 'text', advice)], files=files)


def t_state(window, turn, sample, attempt, advice, files, *, code=None, **reply):
    code = code or {'main.py': PASS}
    t = f'windows/{window}/forks/0/turns/{turn}/ts/{sample}'
    path = f'{t}/attempts/{attempt}'
    return State(T(code, thinking='Write main.py.', text='Done.', **reply),
                 sent=t_sent(path, advice), logs=[(t, 'thinking', 'Write main.py.'), (t, 'text', 'Done.')],
                 files={**files, f'{path}/stdout.txt': STDOUT, **{f'{path}/src/{name}': text for name, text in code.items()}})


def attempt(window, turn, sample, number=0):
    return f'windows/{window}/forks/0/turns/{turn}/ts/{sample}/attempts/{number}'


def opened(window):
    return {f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}


def advised(window, turn, advice, score=None):
    digest = f'advices/{sha256(advice.encode()).hexdigest()}'
    path = f'windows/{window}/forks/0/turns/{turn}'
    files = {f'{path}/metadata.json': {'advice': digest}}
    if score is not None:
        files |= {f'{digest}/advice.txt': advice, f'{digest}/advice.json': {'score': score}}
    return files


def evaluated(*paths):
    return {path: content for p in paths for path, content in results(p, PASS).items()}


def timed_out(path):
    return {f'{path}/generation.json': {'timed_out': True}}


def solved(config, path, attempts):
    solution = config.output / path / 'src'
    return {'result.json': {'success': True, 'attempts': attempts, 'solution': str(solution)}}


async def test_retries_a_hung_sample_once_with_a_fresh_t(config, execute_run_experiment):
    config.t_samples = 3
    config.t_sample_timeout = .1
    config.t_sample_retries = 1
    world = [
        u_state(config, 0, 0, None, 'Double.', {'settings.json': ..., **opened(0)}),
        t_state(0, 0, 0, 0, 'Double.', {**advised(0, 0, 'Double.', 7)}),
        t_state(0, 0, 1, 0, 'Double.', {}, code={'partial.py': 'partial'}, hang=True),
        t_state(0, 0, 2, 0, 'Double.', {}),
        t_state(0, 0, 1, 1, 'Double.', {**evaluated(attempt(0, 0, 0), attempt(0, 0, 2)), **timed_out(attempt(0, 0, 1))}),
        u_state(config, 1, 0, None, 'Double.', {**evaluated(attempt(0, 0, 1, 1)), **opened(1)}, previous=len('Double.')),
        t_state(1, 0, 0, 0, 'Double.', {**advised(1, 0, 'Double.')}),
        t_state(1, 0, 1, 0, 'Double.', {}),
        t_state(1, 0, 2, 0, 'Double.', {}),
        Done(outcome=config.output / attempt(0, 0, 0) / 'src', files={
            **evaluated(*(attempt(1, 0, sample) for sample in range(3))), **solved(config, attempt(0, 0, 0), 2)}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_counts_a_sample_that_hangs_twice_as_failed_and_keeps_running(config, execute_run_experiment):
    config.max_u_turns = 2
    config.t_samples = 3
    config.t_sample_timeout = .1
    config.t_sample_retries = 1
    long = 'Double the input.'
    world = [
        u_state(config, 0, 0, None, long, {'settings.json': ..., **opened(0)}),
        t_state(0, 0, 0, 0, long, {**advised(0, 0, long, 17)}),
        t_state(0, 0, 1, 0, long, {}),
        t_state(0, 0, 2, 0, long, {}),
        u_state(config, 0, 1, None, 'Double.', {**evaluated(*(attempt(0, 0, sample) for sample in range(3)))}),
        t_state(0, 1, 0, 0, 'Double.', {**advised(0, 1, 'Double.', 7)}),
        t_state(0, 1, 1, 0, 'Double.', {}),
        t_state(0, 1, 2, 0, 'Double.', {}, hang=True),
        t_state(0, 1, 2, 1, 'Double.', {**evaluated(attempt(0, 1, 0), attempt(0, 1, 1)), **timed_out(attempt(0, 1, 2))},
                hang=True),
        u_state(config, 1, 0, None, long, {**timed_out(attempt(0, 1, 2, 1)), **opened(1)}, previous=len(long)),
        t_state(1, 0, 0, 0, long, {**advised(1, 0, long)}),
        t_state(1, 0, 1, 0, long, {}),
        t_state(1, 0, 2, 0, long, {}),
        u_state(config, 1, 1, None, long, {**evaluated(*(attempt(1, 0, sample) for sample in range(3)))}, previous=len(long)),
        t_state(1, 1, 0, 0, long, {**advised(1, 1, long)}),
        t_state(1, 1, 1, 0, long, {}),
        t_state(1, 1, 2, 0, long, {}),
        Done(outcome=config.output / attempt(0, 0, 0) / 'src', files={
            **evaluated(*(attempt(1, 1, sample) for sample in range(3))), **solved(config, attempt(0, 0, 0), 4)}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_gives_queued_samples_their_own_full_budget(config, execute_run_experiment):
    config.t_samples = 3
    config.t_pool_size = 1
    config.t_sample_timeout = .2
    best = flush(0, 'Double.', length=7, codes=[PASS] * 3)
    states, pending = played([[(QUESTION, 'Double.', [PASS] * 3)], [(best, 'Double.', [PASS] * 3)]],
                             {'Double.': {'score': 7}}, sequential=True, config=config)
    for state in states:
        if isinstance(state.reply, T):
            state.reply.seconds = .1
    async with execute_run_experiment(config, [*states, outcome(config, 'windows/0/forks/0/turns/0', 2, pending)]):
        pass


async def test_does_not_retry_with_a_zero_budget(config, execute_run_experiment):
    config.t_sample_retries = 0
    config.t_sample_timeout = .05
    partial = {'partial.py': 'partial'}
    world = [
        u_state(config, 0, 0, None, 'Double.', {'settings.json': {**settings(config), 't_sample_timeout': .05, 't_sample_retries': 0,
                                                             'max_u_turns': config.max_u_turns}, **opened(0)}),
        t_state(0, 0, 0, 0, 'Double.', {**advised(0, 0, 'Double.', 7)},
                code=partial, hang=True),
        u_state(config, 1, 0, None, 'Double.', {**timed_out(attempt(0, 0, 0)), **opened(1)}),
        t_state(1, 0, 0, 0, 'Double.', {**advised(1, 0, 'Double.')},
                code=partial, hang=True),
        Done(outcome=None, files={**timed_out(attempt(1, 0, 0)), 'error.txt': 'No passing solution after 2 U turns\n',
                                  'result.json': {'success': False, 'attempts': 2, 'solution': None}}),
    ]
    async with execute_run_experiment(config, world):
        pass


@pytest.fixture
def in_tmp_path(tmp_path):
    with chdir(tmp_path):
        yield


@pytest.mark.parametrize('phase', [U, T])
async def test_cancels_and_cleans_up_on_sigterm(config, tmp_path, in_tmp_path, execute_run_experiment, phase):
    (tmp_path / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
    asked = played([[(QUESTION, 'Double.', [PASS])]], {'Double.': {'score': 7}},
                   config=config.model_copy(update={'max_u_turns': None}))[0][0]
    asked.sent['model'] = U_MODEL
    asked.logs = []
    world = [asked] if phase is T else []
    argv = ['--window-forks', '1', '--output', str(config.output), '--t-samples', '1', str(config.problem_dir)]
    async with execute_run_experiment(config, world, run=main(argv)) as run:
        run.release()
        await run.idle()
        assert run.waiting == [phase]
        run.killed = True
        signal.raise_signal(signal.SIGTERM)
        with pytest.raises(asyncio.CancelledError):
            await run.task
