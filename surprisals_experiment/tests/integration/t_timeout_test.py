"""Hung T samples retry and real CLI SIGTERM cancels both model phases."""
import asyncio
import signal
from contextlib import chdir
from hashlib import sha256
from unittest.mock import patch
import httpx2
import pytest

from openai import AsyncOpenAI
from fake_botbox import FakeSession
from surprisals_experiment.cli.main import main
from run_state_machine_test import settings
from u_flush_test import PASS, QUESTION, STDOUT, chat, flush, outcome, played, results
from utils.world import U, Done, State, T, t_sent, u_system


def u_state(config, window, turn, prompt, advice, files, previous=None):
    path = f'windows/{window}/forks/0/turns/{turn}'
    return State(U(advice, thinking='Think.'),
                 sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                       'messages': [{'role': 'system', 'content': u_system(config, turn + 1, previous)},
                                    {'role': 'user', 'content': prompt}]},
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
    files = {f'{path}/metadata.json': {'advice': digest}, f'{path}/u/advice.txt': advice}
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
    best = flush(0, 'Double.', length=7, codes=[PASS] * 3)
    world = [
        u_state(config, 0, 0, QUESTION, 'Double.', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t_state(0, 0, 0, 0, 'Double.', {**chat(0, (QUESTION, 'Double.')), **advised(0, 0, 'Double.', 7)}),
        t_state(0, 0, 1, 0, 'Double.', {}, code={'partial.py': 'partial'}, hang=True),
        t_state(0, 0, 2, 0, 'Double.', {}),
        t_state(0, 0, 1, 1, 'Double.', {**evaluated(attempt(0, 0, 0), attempt(0, 0, 2)), **timed_out(attempt(0, 0, 1))}),
        u_state(config, 1, 0, best, 'Double.', {**evaluated(attempt(0, 0, 1, 1)), **opened(1), **chat(1, (best, None))}, previous=len('Double.')),
        t_state(1, 0, 0, 0, 'Double.', {**chat(1, (best, 'Double.')), **advised(1, 0, 'Double.')}),
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
    best = flush(0, long, length=17, codes=[PASS] * 3)
    world = [
        u_state(config, 0, 0, QUESTION, long, {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t_state(0, 0, 0, 0, long, {**chat(0, (QUESTION, long)), **advised(0, 0, long, 17)}),
        t_state(0, 0, 1, 0, long, {}),
        t_state(0, 0, 2, 0, long, {}),
        u_state(config, 0, 1, best, 'Double.', {**evaluated(*(attempt(0, 0, sample) for sample in range(3))),
                                        **chat(0, (QUESTION, long), (best, None))}),
        t_state(0, 1, 0, 0, 'Double.', {**chat(0, (QUESTION, long), (best, 'Double.')), **advised(0, 1, 'Double.', 7)}),
        t_state(0, 1, 1, 0, 'Double.', {}),
        t_state(0, 1, 2, 0, 'Double.', {}, hang=True),
        t_state(0, 1, 2, 1, 'Double.', {**evaluated(attempt(0, 1, 0), attempt(0, 1, 1)), **timed_out(attempt(0, 1, 2))},
                hang=True),
        u_state(config, 1, 0, best, long, {**timed_out(attempt(0, 1, 2, 1)), **opened(1), **chat(1, (best, None))}, previous=len(long)),
        t_state(1, 0, 0, 0, long, {**chat(1, (best, long)), **advised(1, 0, long)}),
        t_state(1, 0, 1, 0, long, {}),
        t_state(1, 0, 2, 0, long, {}),
        u_state(config, 1, 1, best, long, {**evaluated(*(attempt(1, 0, sample) for sample in range(3))),
                                   **chat(1, (best, long), (best, None))}, previous=len(long)),
        t_state(1, 1, 0, 0, long, {**chat(1, (best, long), (best, long)), **advised(1, 1, long)}),
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
        u_state(config, 0, 0, QUESTION, 'Double.', {'settings.json': {**settings(config), 't_sample_timeout': .05, 't_sample_retries': 0,
                                                             'max_u_turns': config.max_u_turns},
                                           **opened(0), **chat(0, (QUESTION, None))}),
        t_state(0, 0, 0, 0, 'Double.', {**chat(0, (QUESTION, 'Double.')), **advised(0, 0, 'Double.', 7)},
                code=partial, hang=True),
        u_state(config, 1, 0, QUESTION, 'Double.', {**timed_out(attempt(0, 0, 0)), **opened(1), **chat(1, (QUESTION, None))}),
        t_state(1, 0, 0, 0, 'Double.', {**chat(1, (QUESTION, 'Double.')), **advised(1, 0, 'Double.')},
                code=partial, hang=True),
        Done(outcome=None, files={**timed_out(attempt(1, 0, 0)), 'error.txt': 'No passing solution after 2 U turns\n',
                                  'result.json': {'success': False, 'attempts': 2, 'solution': None}}),
    ]
    async with execute_run_experiment(config, world):
        pass


@pytest.fixture
def started():
    return asyncio.Event()


@pytest.fixture
def blocked(request, started):
    async def block(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    def client(**kwargs):
        return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(block)))

    with (patch('surprisals_experiment.sdk.utils.u_chat.opener.AsyncOpenAI', client) if request.param == 'U'
          else patch.object(FakeSession, 'message', block)):
        yield


@pytest.fixture
def in_tmp_path(tmp_path):
    with chdir(tmp_path):
        yield


@pytest.mark.parametrize('blocked', ['U', 'T'], indirect=True)
async def test_cancels_and_cleans_up_on_sigterm(config, botbox_script, tmp_path, in_tmp_path, started, blocked):
    (tmp_path / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
    botbox_script.advice.append('Double.')
    task = asyncio.create_task(main([
        '--output', str(config.output), '--t-samples', '1', '--t-sample-timeout', '1.5',
        str(config.problem_dir),
    ]))
    try:
        await asyncio.wait_for(started.wait(), 5)
        signal.raise_signal(signal.SIGTERM)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert all(s.closed for s in botbox_script.sessions)
        assert config.u_transcripts.joinpath('messages.jsonl').exists()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
