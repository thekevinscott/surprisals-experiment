"""Window stopping uses persisted successful scores across the whole run."""

from hashlib import sha256

import pytest

from state_machine.testing import Done, State
from surprisals_experiment.config import Config
from utils.world import U, Score, T, t_sent, u_system

QUESTION = 'Read an integer and print its double.'
DOUBLE = 'print(int(input()) * 2)'


def settings(config):
    return {'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
            'u_thinking': 'high', 'u_provider': 'xiaomi', 't_model': 't', 't_provider': 'coreweave/fp4', 'cap_strategy': config.cap_strategy,
            'scorer_base_url': config.scorer_base_url, 'scorer_model': 'openai/gpt-oss-120b', 't_samples': config.t_samples, 't_pool_size': 3,
            't_sample_timeout': 900.0, 't_sample_retries': 3, 'infra_retries': 0, 'window_forks': 1, 'fork_turns': 10,
            'window_solo_turns': 30, 'max_u_turns': 1, 'git_commit': ...}


def u_body(config, user, best):
    return {'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
            'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
            'messages': [{'role': 'system', 'content': u_system(config, 1, best)}, {'role': 'user', 'content': user}]}


def asked(user):
    return [{'role': 'system', 'content': ...}, {'role': 'system', 'content': ...},
            {'role': 'user', 'content': user, '_reset': True}]


def answered(user, advice):
    return [*asked(user), {'content': advice, 'role': 'assistant', 'reasoning': 'Think.', '_complete': True}]


def stdout():
    return [{'type': 'message_update', 'assistantMessageEvent': {'type': 'thinking_delta', 'delta': 'Code.'}},
            {'type': 'message_update', 'assistantMessageEvent': {'type': 'text_delta', 'delta': 'Done.'}}]


def results(passed):
    out = ['6\n', '14\n'] if passed else ['0\n', '0\n']
    return {'duration_seconds': 0.0, 'passed': 2 if passed else 0, 'failed': 0 if passed else 2, 'total': 2,
            'all_passed': passed, 'cases': [
                {'index': index, 'passed': passed, 'status': 'passed' if passed else 'wrong_answer',
                 'stdout': printed, 'stderr': '', 'exit_code': 0} for index, printed in enumerate(out)]}


def attempt(measure, advice, bits, codes):
    length = f'<length>{len(advice)} characters</length>\n' if measure == 'characters' else ''
    score = '' if measure == 'characters' else f'<bits>\n{advice}<{bits:.1f}>\n</bits>\n'
    code = ''.join(f'<T-{index}>\n<file path="main.py">\n{source}\n</file>\n2/2 test cases passed\n</T-{index}>\n'
                   for index, source in enumerate(codes))
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>0</index>\n'
            f'{length}<advice>\n{advice}\n</advice>\n{score}<code>\n{code}</code>\n</attempt>')


def window_world(config, windows):
    """`windows` is a list of (advice, bits, codes); every T sample writes its code into main.py."""
    measure = config.cap_strategy
    world = []
    best = None
    scored = set()
    previous = {}
    for window, (advice, bits, codes) in enumerate(windows):
        turn = f'windows/{window}/forks/0/turns/0'
        u_dir = 'u/transcripts' if window == 0 else f'windows/{window}/forks/0/u/transcripts'
        user = QUESTION if best is None else attempt(measure, *best[1:])
        record = sha256(advice.encode()).hexdigest()
        files = previous | {f'{u_dir}/messages.jsonl': asked(user),
                            f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}
        if window == 0:
            files['settings.json'] = settings(config)
        world.append(State(U(advice, thinking='Think.'), sent=u_body(config, user, best and best[2]),
                           logs=[(f'{turn}/u', 'thinking', 'Think.'), (f'{turn}/u', 'text', advice)], files=files))
        pending = {f'{u_dir}/messages.jsonl': answered(user, advice),
                   f'{u_dir}/usage.jsonl': [{'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}],
                   f'{turn}/metadata.json': {'advice': f'advices/{record}'},
                   f'{turn}/u/advice.txt': advice}
        if record not in scored:
            scored.add(record)
            pending[f'advices/{record}/advice.txt'] = advice
            if measure == 'surprisal':
                world.append(State(Score([(advice, bits)]), sent=advice,
                                   files={**pending, f'advices/{record}/advice.json': {}}))
                pending = {}
            pending[f'advices/{record}/advice.json'] = ({'score': bits} if measure == 'characters' else
                                                        {'score': pytest.approx(bits), 'tokens': [[advice, pytest.approx(bits)]]})
        for sample, source in enumerate(codes):
            files = {f'{turn}/ts/{sample}/attempts/0/stdout.txt': stdout(), f'{turn}/ts/{sample}/attempts/0/src/main.py': source}
            if sample == 0:
                files |= pending
            world.append(State(T({'main.py': source}, thinking='Code.', text='Done.'),
                               sent=t_sent(f'{turn}/ts/{sample}/attempts/0', advice),
                               logs=[(f'{turn}/ts/{sample}', 'thinking', 'Code.'),
                                     (f'{turn}/ts/{sample}', 'text', 'Done.')], files=files))
        previous = {}
        for sample, source in enumerate(codes):
            previous |= {f'{turn}/ts/{sample}/attempts/0/generation.json': {'exit_code': 0},
                         f'{turn}/ts/{sample}/attempts/0/tests.json': results(source == DOUBLE)}
        if all(source == DOUBLE for source in codes) and (best is None or bits < best[2]):
            best = (window, advice, bits, codes)
    solution = config.output / f'windows/{best[0]}/forks/0/turns/0/ts/0/attempts/0/src' if best else None
    result = {'success': best is not None, 'attempts': len(windows), 'solution': str(solution) if best else None}
    if measure == 'surprisal':
        result |= {'cap_strategy': 'surprisal', 'best_measurement': best[2] if best else None, 'scorer_model': 'openai/gpt-oss-120b',
                   'scorer_base_url': 'http://scorer/v1'}
    if not best:
        previous['error.txt'] = f'No passing solution after {len(windows)} U turns\n'
    world.append(Done(outcome=solution, files=previous | {'result.json': result}))
    return world


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
@pytest.mark.parametrize('scores,passed,windows,best', [
    ([100, 96], [True, True], 2, 1),
    ([100, 95, 95], [True, True, True], 3, 1),
    ([100, 90, 90], [True, True, True], 3, 1),
    ([100, 100], [True, True], 2, 0),
    ([100, 110], [True, True], 2, 0),
    ([100, 90, 96], [True, True, True], 3, 1),
    ([100, 1], [True, False], 2, 0),
    ([100, 90, 90], [False, True, True], 3, 1),
    ([100, 90], [False, False], 2, None),
], ids=['under-five', 'exactly-five', 'over-five', 'equal', 'worse',
        'cumulative-best', 'failed-lower-score', 'first-success-later', 'no-success'])
async def test_window_stop(config, execute_run_experiment, measure, scores, passed, windows, best):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1', 't_samples': 2,
    }))
    attempts = []
    for score, success in zip(scores, passed):
        advice = 'x' * score if measure == 'characters' else f'score {score}'
        attempts.append((advice, score if measure == 'characters' else score / 10,
                         [DOUBLE, DOUBLE if success else 'print(0)']))
    world = window_world(config, attempts)
    expected = config.output / f'windows/{best}/forks/0/turns/0/ts/0/attempts/0/src' if best is not None else None
    assert world[-1].outcome == expected
    assert len(world) == windows * 3 + 1 + (measure == 'surprisal') * len(set(scores))
    async with execute_run_experiment(config, world):
        pass
    async with execute_run_experiment(config, [Done(outcome=expected)]):
        pass


async def test_zero_best_score_stops_after_two_windows(config, execute_run_experiment):
    config = Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
    }))
    world = window_world(config, [('zero', 0.0, [DOUBLE])] * 2)
    assert world[-1].outcome == config.t_dir(0, 0) / 'attempts/0/src'
    async with execute_run_experiment(config, world):
        pass
