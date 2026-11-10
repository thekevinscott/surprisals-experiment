"""A window completes its fork and does not ask U again once finished."""

from hashlib import sha256

import pytest

from state_machine.testing import Done, State
from u_flush_test import PASS, flush, outcome, played
from utils.world import U, T, t_sent, u_system


QUESTION = 'Read an integer and print its double.'
DOUBLE = 'print(int(input()) * 2)\n'
USAGE = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}


def suite(passed):
    return {'duration_seconds': 0.0, 'passed': 2 if passed else 0, 'failed': 0 if passed else 2, 'total': 2,
            'all_passed': passed, 'cases': [
                {'index': index, 'passed': passed, 'status': 'passed' if passed else 'wrong_answer',
                 'stdout': stdout if passed else '0\n', 'stderr': '', 'exit_code': 0}
                for index, stdout in enumerate(['6\n', '14\n'])]}


def stdout():
    return ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write main.py."}}\n'
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')


def prompt(best):
    if best is None:
        return QUESTION
    position, advice = best
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>{position}</index>\n'
            f'<length>{len(advice)} characters</length>\n<advice>\n{advice}\n</advice>\n<code>\n<T-0>\n'
            f'<file path="main.py">\n{DOUBLE}</file>\n<results>2/2 test cases passed</results>\n</T-0>\n</code>\n</attempt>')


def run_world(config, rounds, advice, code):
    """States for `rounds` of (window, position, forks): U for each fork in order, then T for each fork.

    Each fork's conversation opens with the best attempt from earlier windows and grows by turn.
    Returns the states and the files the last T round leaves for Done.
    """
    states, pending, transcripts, written, best, starts, conversations = [], {}, {}, set(), None, {}, {}
    for window, position, forks in rounds:
        start = starts.setdefault(window, best)
        for fork in forks:
            text = advice(fork, position)
            turn = f'windows/{window}/forks/{fork}/turns/{position}'
            path = 'u/transcripts' if (window, fork) == (0, 0) else f'windows/{window}/forks/{fork}/u/transcripts'
            conversation = conversations.setdefault((window, fork), [{'role': 'user', 'content': prompt(start)}])
            messages = transcripts.setdefault(path, [])
            messages += [{'role': 'system', 'content': ...}] * (1 if messages else 2)
            messages += [{**conversation[0], '_reset': True}, *conversation[1:]]
            files = {**pending, f'{path}/messages.jsonl': list(messages)}
            if not states:
                files['settings.json'] = {
                    'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
                    'u_thinking': 'high', 'u_provider': 'xiaomi', 't_model': 't', 't_provider': 'coreweave/fp4', 'cap_strategy': 'characters', 'scorer_base_url': None, 'scorer_model': 'openai/gpt-oss-120b',
                    't_samples': 1, 't_pool_size': 3, 't_sample_timeout': 900.0, 't_sample_retries': 3, 'infra_retries': 0,
                    'window_forks': config.window_forks, 'fork_turns': config.fork_turns,
                    'window_solo_turns': config.window_solo_turns, 'max_u_turns': config.max_u_turns,
                    'git_commit': ...,
                }
            if position == 0:
                files[f'windows/{window}/forks/{fork}/fork.json'] = {}
                if fork == 0:
                    files[f'windows/{window}/window.json'] = {}
            states.append(State(
                U(text, thinking='Shorten.'),
                sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                      'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
                      'messages': [{'role': 'system', 'content': u_system(config, position + 1, start and len(start[1]))},
                                   *conversation]},
                logs=[(f'{turn}/u', 'thinking', 'Shorten.'), (f'{turn}/u', 'text', text)],
                files=files,
            ))
            messages.append({'content': text, 'role': 'assistant', 'reasoning': 'Shorten.', '_complete': True})
            stored = 'advices/' + sha256(text.encode()).hexdigest()
            pending = {
                f'{turn}/metadata.json': {'advice': stored},
                f'{turn}/u/advice.txt': text,
                f'{path}/messages.jsonl': list(messages),
                f'{path}/usage.jsonl': [USAGE] * sum('_complete' in message for message in messages),
            }
            if stored not in written:
                written.add(stored)
                pending |= {f'{stored}/advice.txt': text, f'{stored}/advice.json': {'score': len(text)}}
        scored = {}
        for fork in forks:
            text = advice(fork, position)
            t = f'windows/{window}/forks/{fork}/turns/{position}/ts/0'
            attempt = f'{t}/attempts/0'
            states.append(State(
                T({'main.py': code(fork)}, thinking='Write main.py.', text='Done.'),
                sent=t_sent(attempt, text),
                logs=[(t, 'thinking', 'Write main.py.'), (t, 'text', 'Done.')],
                files={**pending, f'{attempt}/stdout.txt': stdout(), f'{attempt}/src/main.py': code(fork)},
            ))
            pending = {}
            passed = code(fork) == DOUBLE
            conversations[window, fork] += [{'role': 'assistant', 'content': text}, {'role': 'user', 'content': (
                f'<code>\n<T-0>\n<file path="main.py">\n{code(fork)}</file>\n<results>{2 * passed}/2 test cases passed</results>\n</T-0>\n</code>')}]
            scored |= {f'{attempt}/generation.json': {'exit_code': 0}, f'{attempt}/tests.json': suite(passed)}
            if passed and (best is None or len(text) < len(best[1])):
                best = (position, text)
        pending = scored
    return states, pending


async def test_finished_run_rerun_does_not_ask_u(config, execute_run_experiment):
    world, scored = run_world(config, [(0, 0, [0]), (1, 0, [0])], lambda fork, position: 'Double it.',
                              lambda fork: DOUBLE)
    solution = config.t_dir(0, 0) / 'attempts/0/src'
    result = {'success': True, 'attempts': 2, 'solution': str(solution)}
    async with execute_run_experiment(config, [*world, Done(outcome=solution, files={**scored, 'result.json': result})]):
        pass

    async with execute_run_experiment(config, [Done(outcome=solution)]):
        pass


@pytest.mark.parametrize('passes', [True, False])
@pytest.mark.parametrize('window_solo_turns', [0, 2])
async def test_parallel_forks_then_winner_continues(config, execute_run_experiment, passes, window_solo_turns):
    config.window_forks = 4
    config.fork_turns = 2
    config.window_solo_turns = window_solo_turns
    config.max_u_turns = None
    winner = 2 if passes else 0
    rounds = [(window, position, forks) for window in range(2) for position, forks in [
        *((position, range(4)) for position in range(2)),
        *((position, [winner]) for position in range(2, 2 + window_solo_turns)),
    ]]
    world, scored = run_world(config, rounds, lambda fork, position: chr(65 + fork) * ([20, 3, 8, 12][fork] - position),
                              lambda fork: DOUBLE if passes and fork != 1 else 'print(0)\n')
    solution = (config.output / f'windows/0/forks/{winner}/turns/{1 + window_solo_turns}/ts/0/attempts/0/src'
                if passes else None)
    attempts = 2 * (8 + window_solo_turns)
    scored['result.json'] = {'success': passes, 'attempts': attempts, 'solution': solution and str(solution)}
    if not passes:
        scored['error.txt'] = f'No passing solution after {attempts} U turns\n'
    async with execute_run_experiment(config, [*world, Done(outcome=solution, files=scored)]):
        pass

    async with execute_run_experiment(config, [Done(outcome=solution)]):
        pass


async def test_later_window_preserves_global_best(config, execute_run_experiment):
    world, pending = played([[(QUESTION, 'A', [PASS])], [(flush(0, 'A', length=1), 'Longer advice', [PASS])]],
                            {'A': {'score': 1}, 'Longer advice': {'score': 13}}, config=config)
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 2, pending))
    async with execute_run_experiment(config, world):
        pass


async def test_parallel_windows_obey_run_stop_rule(config, execute_run_experiment):
    config.window_forks = 4
    config.fork_turns = 1
    config.window_solo_turns = 1
    config.max_u_turns = None
    rounds = [(window, position, forks) for window in range(2) for position, forks in [(0, range(4)), (1, [0])]]
    world, scored = run_world(config, rounds, lambda fork, position: 'Double.', lambda fork: DOUBLE)
    solution = config.t_dir(0, 0) / 'attempts/0/src'
    result = {'success': True, 'attempts': 10, 'solution': str(solution)}
    async with execute_run_experiment(config, [*world, Done(outcome=solution, files={**scored, 'result.json': result})]):
        pass
