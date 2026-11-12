"""Flush shows the original question and only the earliest shortest all-pass attempt."""

from hashlib import sha256

import pytest
from state_machine.testing import Done, State
from surprisals_experiment.config import Config
from surprisals_experiment.prompt import PROMPTS
from utils.world import Score, T, U, t_sent, u_system, u_user

PASS = 'print(int(input()) * 2)\n'
OTHER_PASS = 'n = int(input())\nprint(n + n)\n'
FAIL = 'print(0)\n'
QUESTION = '<original_question>\nRead an integer and print its double.\n</original_question>'
STDOUT = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write main.py."}}\n'
          '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')


def flush(index, advice, *, length=None, bits=None, codes=(PASS,)):
    code = '\n'.join(f'<T-{sample}>\n<file path="main.py">\n{source.rstrip()}\n</file>\n<results>2/2 test cases passed</results>\n</T-{sample}>'
                     for sample, source in enumerate(codes))
    return (f'{QUESTION}\n\n<attempt>\n<index>{index}</index>\n'
            + f'<advice>\n{advice}\n</advice>\n'
            + (f'<length>{length} characters</length>\n' if length else '')
            + (f'<bits>\n{bits}\n</bits>\n' if bits else '')
            + f'<code>\n{code}\n</code>\n</attempt>')


def appended(*codes):
    """One earlier turn's T results, as appended to U's conversation."""
    return '<code>\n' + ''.join(
        f'<T-{sample}>\n<file path="main.py">\n{source.rstrip()}\n</file>\n<results>{0 if source == FAIL else 2}/2 test cases passed</results>\n'
        f'</T-{sample}>\n' for sample, source in enumerate(codes)) + '</code>'


def chat(window, *turns, config, best=None):
    """The window's U transcript after `turns` of (prompt, advice); advice None while U is still asked.

    A prompt is raw opening text, or a conversation whose user messages already include turn lines."""
    usage = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
    lines = [{'role': 'system', 'content': u_system(config)}]
    for attempt, (user, advice) in enumerate(turns):
        conversation = user if isinstance(user, list) else [{'role': 'user', 'content': u_user(config, attempt + 1, user, best)}]
        lines.append(conversation[-1] | {'_attempt': attempt})
        if advice is not None:
            lines.append({'role': 'assistant', 'content': advice, 'reasoning': 'Think.', **usage})
    transcripts = f'windows/{window}/forks/0/u'
    return {f'{transcripts}/transcript.jsonl': lines}


def results(path, code):
    outputs = ['0\n', '0\n'] if code == FAIL else ['6\n', '14\n']
    cases = [{'index': index, 'passed': code != FAIL, 'status': 'wrong_answer' if code == FAIL else 'passed',
              'stdout': stdout, 'stderr': '', 'exit_code': 0} for index, stdout in enumerate(outputs)]
    passed = 0 if code == FAIL else 2
    return {f'{path}/generation.json': {'exit_code': 0}, f'{path}/tests.json': {
        'duration_seconds': 0.0, 'passed': passed, 'failed': 2 - passed, 'total': 2, 'all_passed': passed == 2,
        'cases': cases}}


def played(windows, scores, *, config, sequential=False, bits=None):
    """States for `windows`, each a list of turns (prompt, advice, codes), and the test results still due at Done.

    Only a window's first turn has a prompt; later turns are None and U sees the window's conversation so far.

    `scores` holds each advice's advice.json, and `bits` the scorer's (token, bits) pairs for each advice it prices.
    Test results land after a turn's last sample, or after each sample when T runs one at a time.
    """
    bits = bits or {}
    states, pending, seen, passed = [], {'settings.json': ...}, set(), []
    for window, window_turns in enumerate(windows):
        best = min(passed, default=None)
        pending |= {f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}
        answered, conversation = [], []
        for index, (prompt, advice, codes) in enumerate(window_turns):
            assert (prompt is None) == (index > 0)
            conversation = conversation or [{'role': 'user', 'content': u_user(config, 1, prompt, best)}]
            path = f'windows/{window}/forks/0/turns/{index}'
            states.append(State(
                U(advice, thinking='Think.'),
                sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                      'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
                      'messages': [{'role': 'system', 'content': u_system(config)}, *conversation]},
                logs=[(f'{path}/u', 'thinking', 'Think.'), (f'{path}/u', 'text', advice)],
                files={**pending, **chat(window, *answered, (list(conversation), None), config=config, best=best)},
            ))
            answered.append((list(conversation), advice))
            measurement = (f'<bits>\n{"".join(f"{token}<{value:.1f}>" for token, value in bits[advice])}\n</bits>'
                           if advice in bits else f'<length>{len(advice)} characters</length>')
            conversation += [{'role': 'assistant', 'content': advice},
                             {'role': 'user', 'content': u_user(config, index + 2, measurement + '\n' + appended(*codes), best)}]
            if codes and FAIL not in codes:
                passed.append(getattr(scores[advice]['score'], 'expected', scores[advice]['score']))
            digest = f'advices/{sha256(advice.encode()).hexdigest()}'
            pending = {**chat(window, *answered, config=config, best=best), f'{path}/metadata.json': {'advice': digest}}
            if advice not in seen:
                seen.add(advice)
                pending[f'{digest}/advice.txt'] = advice
                if advice in bits:
                    states.append(State(Score(bits[advice]), sent=advice,
                                        files={**pending, f'{digest}/advice.json': {}}))
                    pending = {}
                pending[f'{digest}/advice.json'] = scores[advice]
            ran = {}
            for sample, code in enumerate(codes):
                t = f'{path}/ts/{sample}'
                attempt = f'{t}/attempts/0'
                states.append(State(
                    T({'main.py': code}, thinking='Write main.py.', text='Done.'), sent=t_sent(attempt, advice),
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


@pytest.mark.parametrize('advices,passed', [
    (['failed first', 'failed second'], [False, False]),
    (['failed first', 'successful advice', 'failed later'], [False, True, False]),
    (['long successful advice', 'short'], [True, True]),
    (['first', 'other'], [True, True]),
    (['best', 'later failure'], [True, False]),
], ids=['no-pass', 'one-pass-among-failures', 'shorter-pass', 'equal-pass', 'failure-after-best'])
async def test_shows_only_best_all_pass_attempt(config, execute_run_experiment, advices, passed):
    config.t_samples = 2
    config.t_pool_size = 1
    config.max_u_turns = len(advices) + 1
    (config.problem_dir / 'question.txt').write_text((config.problem_dir / 'question.txt').read_text() + '\n')
    question = '<original_question>\n' + (config.problem_dir / 'question.txt').read_text().rstrip('\n') + '\n</original_question>'
    texts = [*advices, 'final']
    winner = min((index for index, ok in enumerate([*passed, True]) if ok), key=lambda index: len(texts[index]))
    first = [(question, texts[0], [PASS, OTHER_PASS if passed[0] else FAIL])]
    middle = [(None, advice, [PASS, OTHER_PASS if ok else FAIL]) for advice, ok in zip(advices[1:], passed[1:])]
    best = flush(winner, texts[winner], length=len(texts[winner]), codes=(PASS, OTHER_PASS))
    second = [(best, texts[winner], [PASS, OTHER_PASS]), *[(None, texts[winner], [PASS, OTHER_PASS])] * len(advices)]
    world, pending = played([[*first, *middle, (None, 'final', [PASS, OTHER_PASS])], second],
                            {text: {'score': len(text)} for text in texts}, sequential=True, config=config)
    context = (PROMPTS / 'u/flush/context.txt').read_text()
    world[3 * len(advices)].sent['messages'][0]['content'] = Containing(context)
    world.append(outcome(config, f'windows/0/forks/0/turns/{winner}', 2 * config.max_u_turns, pending))
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_appends_turns_within_a_window_and_flushes_at_the_next(config, execute_run_experiment):
    config.max_u_turns = 3
    world, pending = played([
        [(QUESTION, 'double it', [PASS]), (None, 'double', [PASS]), (None, 'ok', [PASS])],
        [(flush(2, 'ok', length=2), 'ok', [PASS]), (None, 'ok', [PASS]), (None, 'ok', [PASS])],
    ], {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}}, config=config)
    world.append(outcome(config, 'windows/0/forks/0/turns/2', 6, pending))
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_selects_by_bits_and_shows_only_best_token_scores(config, execute_run_experiment):
    scores = {'Use a two-pointer': [('Use', 1.123), (' a', 0.4), (' two', 0.3), ('-pointer', 0.2)],
              'Sweep.': [('Sweep', 7.9), ('.', 0.06)], 'done': [('done', 1.0)]}
    config = Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
        'max_u_turns': 3,
    }))
    done = flush(2, 'done', bits='done<1.0>')
    world, pending = played([
        [(QUESTION, 'Use a two-pointer', [PASS]), (None, 'Sweep.', [PASS]), (None, 'done', [PASS])],
        [(done, 'done', [PASS]), (None, 'done', [PASS]), (None, 'done', [PASS])],
    ], {advice: {'score': pytest.approx(sum(bits for _, bits in pairs)),
                 'tokens': [[token, pytest.approx(bits)] for token, bits in pairs]} for advice, pairs in scores.items()},
        bits=scores, config=config)
    world.append(outcome(config, 'windows/0/forks/0/turns/2', 6, pending, best_measurement=1.0,
                         cap_strategy='surprisal', scorer_base_url='http://scorer/v1', scorer_model='openai/gpt-oss-120b'))
    async with execute_run_experiment(config, world, u_layout=True):
        pass


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_shows_only_the_selected_measure_and_no_results(config, execute_run_experiment, measure):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1',
        'max_u_turns': 2, 't_samples': 2,
    }))
    if measure == 'characters':
        best = flush(1, 'next', length=4, codes=(PASS, OTHER_PASS))
        scores = {'double': {'score': 6}, 'next': {'score': 4}}
        bits, scoring = {}, {}
    else:
        best = flush(1, 'next', bits='next<1.0>', codes=(PASS, OTHER_PASS))
        bits = {'double': [('double', 2.5)], 'next': [('next', 1.0)]}
        scores = {advice: {'score': pairs[0][1], 'tokens': [list(pairs[0])]} for advice, pairs in bits.items()}
        scoring = {'best_measurement': 1.0, 'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
                   'scorer_model': 'openai/gpt-oss-120b'}
    world, pending = played([
        [(QUESTION, 'double', [PASS, OTHER_PASS]), (None, 'next', [PASS, OTHER_PASS])],
        [(best, 'next', [PASS, OTHER_PASS]), (None, 'next', [PASS, OTHER_PASS])],
    ], scores, bits=bits, config=config)
    world.append(outcome(config, 'windows/0/forks/0/turns/1', 4, pending, **scoring))
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_omits_large_files_from_the_flush(config, execute_run_experiment):
    config.max_u_turns = 1
    data = 'x' * (1 << 20)
    shown = flush(0, 'double', length=6).replace(
        '<file path="main.py">', f'<file path="data.txt" omitted="{len(data)} bytes"/>\n<file path="main.py">')
    world, _ = played([[(QUESTION, 'double', [PASS])], [(shown, 'ok', [PASS])]], {'double': {'score': 6}, 'ok': {'score': 2}},
                      config=config)
    world[1].reply.files['data.txt'] = data
    world[1].files['windows/0/forks/0/turns/0/ts/0/attempts/0/src/data.txt'] = data
    async with execute_run_experiment(config, world[:3], u_layout=True) as run:
        await run.reached(world[2])
        run.kill()


@pytest.mark.parametrize('measure,measurement', [
    ('characters', '<length>9 characters</length>'),
    ('surprisal', '<bits>\ndouble<2.5> it<1.2>\n</bits>'),
])
async def test_turn_two_contains_previous_advice_measurement(config, execute_run_experiment, measure, measurement):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1', 'max_u_turns': 2,
    }))
    bits = {'double it': [('double', 2.5), (' it', 1.25)]} if measure == 'surprisal' else {}
    scores = {'double it': {'score': 3.75, 'tokens': [['double', 2.5], [' it', 1.25]]}
              if bits else {'score': 9}, 'next': {'score': 4}}
    world, _ = played([[(QUESTION, 'double it', [PASS]), (None, 'next', [PASS])]],
                      scores, bits=bits, config=config)
    second = world[3 if bits else 2]
    second.sent['messages'][-1]['content'] = u_user(config, 2, measurement + '\n' + appended(PASS))
    second.files['windows/0/forks/0/u/transcript.jsonl'][-1]['content'] = u_user(config, 2, measurement + '\n' + appended(PASS))
    async with execute_run_experiment(config, world[:world.index(second) + 1], u_layout=True) as run:
        await run.reached(second)
        run.kill()
