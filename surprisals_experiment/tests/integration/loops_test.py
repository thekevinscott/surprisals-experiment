"""Integration tests through the real U/T adapters and local evaluator."""

from hashlib import sha256

import pytest
from state_machine.testing import Done, State
from utils.world import T, U, t_sent

from surprisals_experiment.config import WINDOW_SOLO_TURNS

QUESTION = 'Read an integer and print its double.'
PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def u_body():
    return {'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'}, 'provider': {'only': ['xiaomi'], 'allow_fallbacks': False}}


def code(sources):
    return '<code>\n' + ''.join(
        f'<T-{t}>\n<file path="main.py">\n{source}</file>\n<results>{2 * (source == PASS)}/2 test cases passed</results>\n</T-{t}>\n'
        for t, source in enumerate(sources)) + '</code>'


def best(index, advice, sources):
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>{index}</index>\n'
            f'<advice>\n{advice}\n</advice>\n<length>{len(advice)} characters</length>\n'
            f'{code(sources)}\n</attempt>')


def evaluation(source):
    passed = source == PASS
    cases = [{'index': i, 'passed': passed, 'status': 'passed' if passed else 'wrong_answer',
              'stdout': out if passed else '0\n', 'stderr': '', 'exit_code': 0}
             for i, out in enumerate(['6\n', '14\n'])]
    return {'duration_seconds': 0.0, 'passed': 2 * passed, 'failed': 2 - 2 * passed, 'total': 2,
            'all_passed': passed, 'cases': cases}


def stdout(thinking):
    return [{'type': 'message_update', 'assistantMessageEvent': {'type': kind, 'delta': delta}}
            for kind, delta in [('thinking_delta', thinking), ('text_delta', 'Done.')]]


def advice_path(advice):
    return f'advices/{sha256(advice.encode()).hexdigest()}'


def run_world(config, turns, *, outcome, attempts):
    """States for `turns`, each (window, U's window opening or None, advice, T sources), then Done."""
    world, evaluated, advices, counts = [], {}, set(), {}
    for window, user, advice, sources in turns:
        turn = counts[window] = counts.get(window, -1) + 1
        fork = f'windows/{window}/forks/0'
        directory = f'{fork}/turns/{turn}'
        files = evaluated
        if not turn:
            files |= {f'windows/{window}/window.json': {}, f'{fork}/fork.json': {}}
        if not world:
            files['settings.json'] = {
                'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
                'u_thinking': 'high', 'u_provider': 'xiaomi', 't_model': 't', 't_provider': 'coreweave/fp4', 'cap_strategy': 'characters', 'scorer_base_url': None, 'scorer_model': 'openai/gpt-oss-120b',
                't_samples': config.t_samples, 't_pool_size': 3, 't_sample_timeout': 900.0, 't_sample_retries': 3, 'infra_retries': 0,
                'window_forks': 1, 'fork_turns': 10, 'window_solo_turns': WINDOW_SOLO_TURNS, 'max_u_turns': config.max_u_turns,
                'git_commit': ...,
            }
        assert (user is None) == bool(turn)
        world.append(State(
            U(advice, thinking='Thinking.'),
            sent=u_body(),
            logs=[(f'{directory}/u', 'thinking', 'Thinking.'), (f'{directory}/u', 'text', advice)],
            files=files,
        ))
        files = {f'{directory}/metadata.json': {'advice': advice_path(advice), 'u_messages': ..., 'u_request_sha256': ...}}
        if advice not in advices:
            advices.add(advice)
            files |= {f'{advice_path(advice)}/advice.txt': advice,
                      f'{advice_path(advice)}/advice.json': {'score': len(advice)}}
        evaluated = {}
        for sample, source in enumerate(sources):
            t = f'{directory}/ts/{sample}'
            attempt = f'{t}/attempts/0'
            world.append(State(
                T({'main.py': source}, thinking='Write main.py.', text='Done.'),
                sent=t_sent(attempt, advice),
                logs=[(t, 'thinking', 'Write main.py.'), (t, 'text', 'Done.')],
                files={**files, f'{attempt}/stdout.txt': stdout('Write main.py.'), f'{attempt}/src/main.py': source},
            ))
            files = {}
            evaluated |= {f'{attempt}/generation.json': {'exit_code': 0}, f'{attempt}/tests.json': evaluation(source)}
    if outcome is None:
        evaluated['error.txt'] = f'No passing solution after {attempts} U turns\n'
    solution = outcome and str(outcome)
    world.append(Done(outcome=outcome, files={
        **evaluated, 'result.json': {'success': outcome is not None, 'attempts': attempts, 'solution': solution},
    }))
    return world


def describe_u_to_t_loop():
    @pytest.mark.parametrize('failures', [0, 2])
    async def it_records_each_batch_with_an_explicit_iteration_limit(config, execute_run_experiment, failures):
        count = failures + 1
        config.max_u_turns = count
        advices = [f'advice {i}' for i in range(2 * count)]
        first = [(0, None if i else QUESTION, advices[i], [FAIL if i < failures else PASS]) for i in range(count)]
        opening = best(failures, advices[failures], [PASS])
        second = [(1, None if i else opening, advices[count + i], [PASS]) for i in range(count)]
        solution = config.output / f'windows/0/forks/0/turns/{failures}/ts/0/attempts/0/src'
        async with execute_run_experiment(config, run_world(config, first + second, outcome=solution,
                                                            attempts=2 * count)):
            pass


def describe_advice_improvement():
    async def it_stops_without_a_first_success(config, execute_run_experiment):
        config.max_u_turns = 2
        turns = [(window, None if turn else QUESTION, 'advice', [FAIL]) for window in [0, 1] for turn in [0, 1]]
        async with execute_run_experiment(config, run_world(config, turns, outcome=None, attempts=4)):
            pass

    @pytest.mark.parametrize('advices,outcomes,best_attempt', [
        (['long advice', 'tiny', 'long advice', 'tiny'], [[PASS, PASS]] * 4, 1),
        (['long advice', 'tiny', 'x'], [[PASS, PASS], [PASS, FAIL], [FAIL, PASS]], 0),
    ])
    async def it_selects_only_strictly_shorter_all_pass_advice(
        config, execute_run_experiment, advices, outcomes, best_attempt,
    ):
        config.max_u_turns = len(advices)
        config.t_samples = 2
        first = [(0, None if i else QUESTION, advice, sources) for i, (advice, sources) in enumerate(zip(advices, outcomes))]
        winner = advices[best_attempt]
        opening = best(best_attempt, winner, [PASS, PASS])
        second = [(1, None if i else opening, winner, [PASS, PASS]) for i in range(len(advices))]
        solution = config.output / f'windows/0/forks/0/turns/{best_attempt}/ts/0/attempts/0/src'
        async with execute_run_experiment(config, run_world(config, first + second, outcome=solution,
                                                            attempts=2 * len(advices))):
            pass


def describe_run_layout():
    async def it_nests_each_turn_under_window_and_fork(config, execute_run_experiment):
        config.max_u_turns = 2
        first = [(0, QUESTION, 'long advice', [PASS]), (0, None, 'short', [PASS])]
        second = [(1, best(1, 'short', [PASS]), 'short', [PASS]), (1, None, 'short', [PASS])]
        solution = config.output / 'windows/0/forks/0/turns/1/ts/0/attempts/0/src'
        async with execute_run_experiment(config, run_world(config, first + second, outcome=solution, attempts=4)):
            pass
