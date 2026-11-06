"""Flush shows the original question and only the earliest shortest all-pass attempt."""

from hashlib import sha256

from surprisals_experiment.prompt import PROMPTS

import pytest

from surprisals_experiment.config import Config
from utils.world import U, Done, State, T

PASS = 'print(int(input()) * 2)\n'
OTHER_PASS = 'n = int(input())\nprint(n + n)\n'
FAIL = 'print(0)\n'
QUESTION = 'Read an integer and print its double.'
STDOUT = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write main.py."}}\n'
          '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')


def flush(index, advice, *, length=None, bits=None, codes=(PASS,)):
    code = '\n'.join(f'<T-{sample}>\n<file path="main.py">\n{source.rstrip()}\n</file>\n</T-{sample}>'
                     for sample, source in enumerate(codes))
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>{index}</index>\n'
            + (f'<length>{length} characters</length>\n' if length else '')
            + f'<advice>\n{advice}\n</advice>\n'
            + (f'<bits>\n{bits}\n</bits>\n' if bits else '')
            + f'<code>\n{code}\n</code>\n</attempt>')


def chat(window, *turns):
    """The window's U transcript after `turns` of (prompt, advice); advice None while U is still asked."""
    lines = [{'role': 'system', 'content': ...}]
    for user, advice in turns:
        lines += [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user, '_reset': True}]
        if advice is not None:
            lines.append({'role': 'assistant', 'content': advice, 'reasoning': 'Think.', '_complete': True})
    transcripts = 'u/transcripts' if window == 0 else f'windows/{window}/forks/0/u/transcripts'
    if turns[-1][1] is None:
        return {f'{transcripts}/messages.jsonl': lines}
    usage = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
    return {f'{transcripts}/messages.jsonl': lines, f'{transcripts}/usage.jsonl': [usage] * len(turns)}


def results(path, code):
    outputs = ['0\n', '0\n'] if code == FAIL else ['6\n', '14\n']
    cases = [{'index': index, 'passed': code != FAIL, 'status': 'wrong_answer' if code == FAIL else 'passed',
              'stdout': stdout, 'stderr': '', 'exit_code': 0} for index, stdout in enumerate(outputs)]
    passed = 0 if code == FAIL else 2
    return {f'{path}/generation.json': {'exit_code': 0}, f'{path}/tests.json': {
        'duration_seconds': 0.0, 'passed': passed, 'failed': 2 - passed, 'total': 2, 'all_passed': passed == 2,
        'cases': cases}}


def played(windows, scores, *, sequential=False):
    """States for `windows`, each a list of turns (prompt, advice, codes), and the test results still due at Done.

    `scores` holds each advice's advice.json. Test results land after a turn's last sample, or after each sample
    when T runs one at a time.
    """
    states, pending, seen = [], {'settings.json': ...}, set()
    for window, turns in enumerate(windows):
        pending |= {f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}
        answered = []
        for index, (prompt, advice, codes) in enumerate(turns):
            path = f'windows/{window}/forks/0/turns/{index}'
            states.append(State(
                U(advice, thinking='Think.'),
                sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                      'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': prompt}]},
                logs=[(f'{path}/u', 'thinking', 'Think.'), (f'{path}/u', 'text', advice)],
                files={**pending, **chat(window, *answered, (prompt, None))},
            ))
            answered.append((prompt, advice))
            digest = f'advices/{sha256(advice.encode()).hexdigest()}'
            pending = {**chat(window, *answered), f'{path}/metadata.json': {'advice': digest},
                       f'{path}/u/advice.txt': advice}
            if advice not in seen:
                seen.add(advice)
                pending |= {f'{digest}/advice.txt': advice, f'{digest}/advice.json': scores[advice]}
            ran = {}
            for sample, code in enumerate(codes):
                t = f'{path}/ts/{sample}'
                attempt = f'{t}/attempts/0'
                states.append(State(
                    T({'main.py': code}, thinking='Write main.py.', text='Done.'), sent=(attempt, advice),
                    logs=[(t, 'thinking', 'Write main.py.'), (t, 'text', 'Done.')],
                    files={**pending, f'{attempt}/stdout.txt': STDOUT, f'{attempt}/src/main.py': code},
                ))
                pending, ran = {}, ran | results(attempt, code)
                if sequential:
                    pending, ran = ran, {}
            pending |= ran
    return states, pending


class Containing(str):
    """Equals any string that contains it."""

    def __eq__(self, other):
        return self in other

    __hash__ = str.__hash__


def outcome(config, path, attempts, pending, **scoring):
    solution = config.output / path / 'ts/0/attempts/0/src'
    return Done(outcome=solution, files={**pending, 'result.json': {
        'success': True, 'attempts': attempts, 'solution': str(solution), **scoring}})


@pytest.mark.parametrize('advices,passed,best', [
    (['failed first', 'failed second'], [False, False], None),
    (['failed first', 'successful advice', 'failed later'], [False, True, False], 1),
    (['long successful advice', 'short'], [True, True], 1),
    (['first', 'other'], [True, True], 0),
    (['best', 'later failure'], [True, False], 0),
], ids=['no-pass', 'one-pass-among-failures', 'shorter-pass', 'equal-pass', 'failure-after-best'])
async def test_shows_only_best_all_pass_attempt(config, execute_run_experiment, advices, passed, best):
    config.t_samples = 2
    config.t_pool_size = 1
    config.max_u_turns = len(advices) + 1
    (config.problem_dir / 'question.txt').write_text((config.problem_dir / 'question.txt').read_text() + '\n')
    question = (config.problem_dir / 'question.txt').read_text()
    if best is None:
        final = question
    else:
        final = flush(best, advices[best], length=len(advices[best]), codes=(PASS, OTHER_PASS))
    texts = [*advices, 'final']
    winner = min((index for index, ok in enumerate([*passed, True]) if ok), key=lambda index: len(texts[index]))
    first = [(question, texts[0], [PASS, OTHER_PASS if passed[0] else FAIL])]
    middle = [(..., advice, [PASS, OTHER_PASS if ok else FAIL]) for advice, ok in zip(advices[1:], passed[1:])]
    second = [(..., texts[winner], [PASS, OTHER_PASS])] * config.max_u_turns
    world, pending = played([[*first, *middle, (final, 'final', [PASS, OTHER_PASS])], second],
                            {text: {'score': len(text)} for text in texts}, sequential=True)
    context = (PROMPTS / 'u/flush/context.txt').read_text()
    world[3 * len(advices)].sent['messages'][0]['content'] = Containing(context)
    world.append(outcome(config, f'windows/0/forks/0/turns/{winner}', 2 * config.max_u_turns, pending))
    async with execute_run_experiment(config, world):
        pass


async def test_sends_no_chat_history(config, execute_run_experiment):
    config.max_u_turns = 3
    best = [flush(0, 'double it', length=9), flush(1, 'double', length=6), flush(2, 'ok', length=2)]
    world, pending = played([
        [(QUESTION, 'double it', [PASS]), (best[0], 'double', [PASS]), (best[1], 'ok', [PASS])],
        [(best[2], 'ok', [PASS])] * 3,
    ], {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}})
    world.append(outcome(config, 'windows/0/forks/0/turns/2', 6, pending))
    async with execute_run_experiment(config, world):
        pass


async def test_selects_by_bits_and_shows_only_best_token_scores(config, scorer_provider, execute_run_experiment):
    scores = [[('Use', 1.123), (' a', 0.4), (' two', 0.3), ('-pointer', 0.2)], [('Sweep', 7.9), ('.', 0.06)],
              [('done', 1.0)]]
    scorer_provider.replies.extend(scores)
    config = Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
        'max_u_turns': 3,
    }))
    two_pointer = flush(0, 'Use a two-pointer', bits='Use<1.1> a<0.4> two<0.3>-pointer<0.2>')
    done = flush(2, 'done', bits='done<1.0>')
    world, pending = played([
        [(QUESTION, 'Use a two-pointer', [PASS]), (two_pointer, 'Sweep.', [PASS]), (two_pointer, 'done', [PASS])],
        [(done, 'done', [PASS])] * 3,
    ], dict.fromkeys(['Use a two-pointer', 'Sweep.', 'done'], ...))
    world.append(outcome(config, 'windows/0/forks/0/turns/2', 6, pending, best_measurement=1.0,
                         cap_strategy='surprisal', scorer_base_url='http://scorer/v1', scorer_model='t'))
    async with execute_run_experiment(config, world):
        pass


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_shows_only_the_selected_measure_and_no_results(config, scorer_provider, execute_run_experiment, measure):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1',
        'max_u_turns': 2, 't_samples': 2,
    }))
    scorer_provider.replies.extend([[('double', 2.5)], [('next', 1.0)]])
    if measure == 'characters':
        double = flush(0, 'double', length=6, codes=(PASS, OTHER_PASS))
        best = flush(1, 'next', length=4, codes=(PASS, OTHER_PASS))
        scores = {'double': {'score': 6}, 'next': {'score': 4}}
        scoring = {}
    else:
        double = flush(0, 'double', bits='double<2.5>', codes=(PASS, OTHER_PASS))
        best = flush(1, 'next', bits='next<1.0>', codes=(PASS, OTHER_PASS))
        scores = {'double': {'score': 2.5, 'tokens': [['double', 2.5]]}, 'next': {'score': 1.0, 'tokens': [['next', 1.0]]}}
        scoring = {'best_measurement': 1.0, 'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
                   'scorer_model': 't'}
    world, pending = played([
        [(QUESTION, 'double', [PASS, OTHER_PASS]), (double, 'next', [PASS, OTHER_PASS])],
        [(best, 'next', [PASS, OTHER_PASS])] * 2,
    ], scores)
    world.append(outcome(config, 'windows/0/forks/0/turns/1', 4, pending, **scoring))
    async with execute_run_experiment(config, world):
        pass
