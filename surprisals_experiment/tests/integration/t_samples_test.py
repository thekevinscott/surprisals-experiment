"""Independent T batches retain sample identity and complete feedback."""
from run_result_test import evaluations, result
from state_machine.testing import State
from u_flush_test import QUESTION, STDOUT, flush, outcome, played
from utils.world import T, t_sent

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'
TURN = 'windows/0/forks/0/turns/0'


def settings(config):
    return {
        'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
        'u_thinking': 'high', 't_model': 't', 'cap_strategy': 'characters', 'scorer_base_url': None,
        't_samples': config.t_samples, 't_pool_size': config.t_pool_size, 't_sample_timeout': 900.0,
        't_sample_retries': 3, 'window_forks': 1, 'fork_turns': 10, 'window_solo_turns': 30,
        'max_u_turns': config.max_u_turns, 'git_commit': ...,
    }


def hung(sample, files=None):
    attempt = f'{TURN}/ts/{sample}/attempts/0'
    return State(T({}, thinking='Write main.py.', text='Done.', hang=True), sent=t_sent(attempt, 'double it'),
                 logs=[(f'{TURN}/ts/{sample}', 'thinking', 'Write main.py.'), (f'{TURN}/ts/{sample}', 'text', 'Done.')],
                 files={**(files or {}), f'{attempt}/stdout.txt': STDOUT})


async def test_requires_every_sample_to_pass(config, execute_run_experiment):
    config.t_samples = 3
    best = flush(0, 'double it', length=9, codes=[PASS] * 3)
    states, pending = played([[(QUESTION, 'double it', [PASS] * 3)], [(best, 'double it', [PASS] * 3)]],
                             {'double it': {'score': 9}}, config=config)
    states[0].files['settings.json'] = settings(config)
    async with execute_run_experiment(config, [*states, outcome(config, TURN, 2, pending)]):
        pass
    assert result(config)['attempts'] == 2
    assert result(config)['solution'] == str(config.output / TURN / 'ts/0/attempts/0/src')
    assert sorted(evaluations(config)) == [f'windows/{window}/forks/0/turns/0/ts/{sample}/attempts/0/tests.json'
                                          for window in range(2) for sample in range(3)]
    assert all(tests['all_passed'] for tests in evaluations(config).values())


async def test_returns_all_outcomes_before_revising_advice(config, execute_run_experiment):
    config.t_samples = 3
    config.max_u_turns = 2
    best = flush(1, 'two', length=3, codes=[PASS] * 3)
    states, pending = played([
        [(QUESTION, 'one', [PASS, FAIL, PASS]), (QUESTION, 'two', [PASS] * 3)],
        [(best, 'two', [PASS] * 3)] * 2,
    ], {'one': {'score': 3}, 'two': {'score': 3}}, config=config)
    async with execute_run_experiment(config, [*states, outcome(config, 'windows/0/forks/0/turns/1', 4, pending)]):
        pass
    assert result(config)['attempts'] == 4
    assert len(evaluations(config)) == 12
    assert [tests['all_passed'] for path, tests in sorted(evaluations(config).items())
            if path.startswith('windows/0/forks/0/turns/0/')] == [True, False, True]


async def test_closes_all_t_sessions_on_cancellation(config, execute_run_experiment):
    config.t_samples = 5
    [asked], pending = played([[(QUESTION, 'double it', [])]], {'double it': {'score': 9}}, config=config)
    world = [asked, hung(0, pending), hung(1), hung(2)]
    async with execute_run_experiment(config, world) as run:
        await run.reached(world[-1])
        run.kill()
    assert not (config.output / 'result.json').exists()


async def test_preserves_partial_batches_without_claiming_success(config, execute_run_experiment):
    config.t_samples = 3
    config.t_pool_size = 1
    states, pending = played([[(QUESTION, 'double it', [PASS])]], {'double it': {'score': 9}}, config=config)
    world = [*states, hung(1, pending)]
    async with execute_run_experiment(config, world) as run:
        await run.reached(world[-1])
        run.kill()
    assert not (config.output / 'result.json').exists()
    assert list(evaluations(config)) == [f'{TURN}/ts/0/attempts/0/tests.json']
