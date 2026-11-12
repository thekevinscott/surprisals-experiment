"""Real chat streaming, feedback, and incident regressions at the HTTP boundary."""

import json
from hashlib import sha256

from state_machine.testing import Done, State
from surprisals_experiment.config import WINDOW_SOLO_TURNS
from u_flush_test import PASS, QUESTION, STDOUT, chat, flush, outcome, played, results
from utils.world import T, U, t_sent, u_system, u_user

USAGE = {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
         'prompt_tokens_details': {'cached_tokens': 50, 'cache_write_tokens': 10},
         'completion_tokens_details': {'reasoning_tokens': 20}, 'cost': 0.000123}
DELAYS = [10, 20, 30, 60, 180, 300, 1200, 1800]
MUTATING = ("from pathlib import Path\nn = input()\nPath('evaluation-only.txt').write_text(n)\n"
            "Path('helper.py').write_text('MUTATED')\nprint(int(n) * 2)\n")


def code(*samples):
    return '<code>\n' + ''.join(f'<T-{sample}>\n' + ''.join(f'<file path="{path}">\n{text.rstrip()}\n</file>\n'
                                                            for path, text in files.items())
                                 + f'<results>2/2 test cases passed</results>\n</T-{sample}>\n' for sample, files in enumerate(samples)) + '</code>'


def prompt(index, advice, *samples):
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>{index}</index>\n'
            f'<length>{len(advice)} characters</length>\n<advice>\n{advice}\n</advice>\n'
            f'{code(*samples)}\n</attempt>')


def exhausted(config, reply, error):
    """U's first try and all 8 retries fail with `error`."""
    sent = {'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
            'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
            'messages': [{'role': 'system', 'content': u_system(config)}, {'role': 'user', 'content': u_user(config, 1, QUESTION)}]}
    u = 'windows/0/forks/0/turns/0/u'
    text = [(u, 'text', reply.text)] if reply.text else []
    first = {'settings.json': ..., 'windows/0/window.json': {}, 'windows/0/forks/0/fork.json': {},
             **chat(0, (QUESTION, None), config=config)}
    return [State(reply, sent=sent, logs=text, files=first),
            *(State(reply, sent=sent, logs=[(u, 'retry', f'{tries}/8 in {delay}s: {error}\n'), *text],
                    files={}) for tries, delay in enumerate(DELAYS, 1)),
            Done(outcome=RuntimeError(f'U chat request failed: {error}; 8 retries exhausted'), files={})]


async def test_feeds_every_t_source_of_the_best_attempt_back(config, execute_run_experiment):
    config.t_samples = 2
    config.max_u_turns = 2
    io = config.problem_dir / 'input_output.json'
    helpers = {'helper.py': 'VALUE = 42\n', 'nested/extra.py': 'EXTRA = 7\n', 'binary.dat': b'\xff', 'hidden.json': io}
    mutated = {'helper.py': 'VALUE = 42\n', 'main.py': MUTATING, 'nested/extra.py': 'EXTRA = 7\n'}
    clean = {'helper.py': 'VALUE = 42\n', 'main.py': PASS, 'nested/extra.py': 'EXTRA = 7\n'}
    best = prompt(1, 'short', clean, clean)
    first = [{'role': 'user', 'content': u_user(config, 1, QUESTION)}, {'role': 'assistant', 'content': 'long advice'},
             {'role': 'user', 'content': u_user(config, 2, code(mutated, clean))}]
    second = [{'role': 'user', 'content': u_user(config, 1, best, 5)}, {'role': 'assistant', 'content': 'short'},
              {'role': 'user', 'content': u_user(config, 2, code(clean, clean), 5)}]

    def turn(window, number):
        return f'windows/{window}/forks/0/turns/{number}'

    def u(window, number, user, advice, files, previous=None):
        path = f'{turn(window, number)}/u'
        return State(U(advice, thinking='Think.'),
                     sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                           'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
                           'messages': [{'role': 'system', 'content': u_system(config)},
                                        *(user if isinstance(user, list) else [{'role': 'user', 'content': u_user(config, number + 1, user, previous)}])]},
                     logs=[(path, 'thinking', 'Think.'), (path, 'text', advice)], files=files)

    def t(window, number, sample, advice, code, files=None):
        ts = f'{turn(window, number)}/ts/{sample}'
        src = {**helpers, 'main.py': code, 'hidden.json': io.read_text()}
        return State(T({'main.py': code, **helpers}, thinking='Write main.py.', text='Done.'),
                     sent=t_sent(f'{ts}/attempts/0', advice),
                     logs=[(ts, 'thinking', 'Write main.py.'), (ts, 'text', 'Done.')],
                     files={**(files or {}), f'{ts}/attempts/0/stdout.txt': STDOUT,
                            **{f'{ts}/attempts/0/src/{name}': text for name, text in src.items()}})

    def advised(window, number, advice, score=None):
        digest = f'advices/{sha256(advice.encode()).hexdigest()}'
        path = turn(window, number)
        files = {f'{path}/metadata.json': {'advice': digest}}
        return files | ({f'{digest}/advice.txt': advice, f'{digest}/advice.json': {'score': score}} if score else {})

    def evaluated(window, number):
        return {path: content for sample in range(2)
                for path, content in results(f'{turn(window, number)}/ts/{sample}/attempts/0', PASS).items()}

    def opened(window):
        return {f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}

    solution = config.output / turn(0, 1) / 'ts/0/attempts/0/src'
    world = [
        u(0, 0, QUESTION, 'long advice', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None), config=config)}),
        t(0, 0, 0, 'long advice', MUTATING, {**chat(0, (QUESTION, 'long advice'), config=config), **advised(0, 0, 'long advice', 11)}),
        t(0, 0, 1, 'long advice', PASS),
        u(0, 1, first, 'short', {**evaluated(0, 0), **chat(0, (QUESTION, 'long advice'), (first, None), config=config)}),
        t(0, 1, 0, 'short', PASS, {**chat(0, (QUESTION, 'long advice'), (first, 'short'), config=config),
                                   **advised(0, 1, 'short', 5)}),
        t(0, 1, 1, 'short', PASS),
        u(1, 0, best, 'short', {**evaluated(0, 1), **opened(1), **chat(1, (best, None), config=config, best=5)}, previous=5),
        t(1, 0, 0, 'short', PASS, {**chat(1, (best, 'short'), config=config, best=5), **advised(1, 0, 'short')}),
        t(1, 0, 1, 'short', PASS),
        u(1, 1, second, 'short', {**evaluated(1, 0), **chat(1, (best, 'short'), (second, None), config=config, best=5)}, previous=5),
        t(1, 1, 0, 'short', PASS, {**chat(1, (best, 'short'), (second, 'short'), config=config, best=5), **advised(1, 1, 'short')}),
        t(1, 1, 1, 'short', PASS),
        Done(outcome=solution, files={**evaluated(1, 1),
                                      'result.json': {'success': True, 'attempts': 4, 'solution': str(solution)}}),
    ]
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_sends_and_records_exact_roles(config, execute_run_experiment):
    config.max_u_turns = 3
    question = 'Read an integer and print its double.'
    best = ('<original_question>\nRead an integer and print its double.\n</original_question>\n\n'
            '<attempt>\n<index>0</index>\n<length>4 characters</length>\n<advice>\ntiny\n</advice>\n'
            '<code>\n<T-0>\n<file path="main.py">\nprint(int(input()) * 2)\n</file>\n<results>2/2 test cases passed</results>\n</T-0>\n</code>\n</attempt>')
    advices = {'tiny': 'advices/8950abfda7b727630760dd35bcf5c3daa7631aff223a90f7728c0d2521dde10c',
               'long advice': 'advices/9cca26ad57d22afe3fb910db6323538932cd68c68ca666f6c97b03ca76f188ab',
               'longer advice': 'advices/6c5930dfdad8282d9030e1cd507d78acfc26231d4fc74758d85584199ee9f561'}
    system = {'role': 'system', 'content': u_system(config)}
    usage = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
    tests = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
        {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
        {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
    ]}
    stdout = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write it."}}\n'
              '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')

    def talk(opening, *said):
        previous = 4 if opening == best else None
        return [{'role': 'user', 'content': u_user(config, 1, opening, previous)},
                *[message for turn, advice in enumerate(said, 2) for message in (
                    {'role': 'assistant', 'content': advice},
                    {'role': 'user', 'content': u_user(config, turn, code({'main.py': PASS}), previous)})]]

    def chat(*turns):
        messages = [system]
        for attempt, (user, advice) in enumerate(turns):
            messages.append(user[-1] | {'_attempt': attempt})
            if advice:
                messages.append({'role': 'assistant', 'content': advice, 'reasoning': 'Think.', **usage})
        return messages

    def transcripts(window):
        return f'windows/{window}/forks/0/u'

    def tested(window, turn):
        return {f'windows/{window}/forks/0/turns/{turn}/ts/0/attempts/0/generation.json': {'exit_code': 0},
                f'windows/{window}/forks/0/turns/{turn}/ts/0/attempts/0/tests.json': tests}

    def u_state(window, turn, user, advice, messages, files):
        return State(
            U(advice, thinking='Think.'),
            sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                  'provider': {'only': ['xiaomi'], 'allow_fallbacks': False},
                  'messages': [{'role': 'system', 'content': u_system(config)}, *user]},
            logs=[(f'windows/{window}/forks/0/turns/{turn}/u', 'thinking', 'Think.'),
                  (f'windows/{window}/forks/0/turns/{turn}/u', 'text', advice)],
            files={f'{transcripts(window)}/transcript.jsonl': messages, **files},
        )

    def t_state(window, turn, advice, messages, files=None):
        t = f'windows/{window}/forks/0/turns/{turn}'
        return State(
            T({'main.py': PASS}, thinking='Write it.', text='Done.'),
            sent=t_sent(f'{t}/ts/0/attempts/0', advice),
            logs=[(f'{t}/ts/0', 'thinking', 'Write it.'), (f'{t}/ts/0', 'text', 'Done.')],
            files={
                f'{transcripts(window)}/transcript.jsonl': messages,
                f'{t}/metadata.json': {'advice': advices[advice]},
                f'{t}/ts/0/attempts/0/stdout.txt': stdout,
                f'{t}/ts/0/attempts/0/src/main.py': PASS,
                **(files or {}),
            },
        )

    def new_advice(advice, score):
        return {f'{advices[advice]}/advice.txt': advice, f'{advices[advice]}/advice.json': {'score': score}}

    solution = config.output / 'windows/0/forks/0/turns/0/ts/0/attempts/0/src'
    world = [
        u_state(0, 0, talk(question), 'tiny', chat((talk(question), None)), {
            'settings.json': {
                'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
                'u_thinking': 'high', 'u_provider': 'xiaomi', 't_model': 't', 't_provider': 'coreweave/fp4', 'cap_strategy': 'characters', 'scorer_base_url': None, 'scorer_model': 'openai/gpt-oss-120b',
                't_samples': 1, 't_pool_size': 3, 't_sample_timeout': 900.0, 't_sample_retries': 3, 'infra_retries': 0,
                'window_forks': 1, 'fork_turns': 10, 'window_solo_turns': WINDOW_SOLO_TURNS, 'max_u_turns': 3,
                'git_commit': ...,
            },
            'windows/0/window.json': {},
            'windows/0/forks/0/fork.json': {},
        }),
        t_state(0, 0, 'tiny', chat((talk(question), 'tiny')), new_advice('tiny', 4)),
        u_state(0, 1, talk(question, 'tiny'), 'long advice', chat((talk(question), 'tiny'), (talk(question, 'tiny'), None)),
                tested(0, 0)),
        t_state(0, 1, 'long advice', chat((talk(question), 'tiny'), (talk(question, 'tiny'), 'long advice')),
                new_advice('long advice', 11)),
        u_state(0, 2, talk(question, 'tiny', 'long advice'), 'longer advice',
                chat((talk(question), 'tiny'), (talk(question, 'tiny'), 'long advice'),
                     (talk(question, 'tiny', 'long advice'), None)), tested(0, 1)),
        t_state(0, 2, 'longer advice', chat((talk(question), 'tiny'), (talk(question, 'tiny'), 'long advice'),
                                            (talk(question, 'tiny', 'long advice'), 'longer advice')),
                new_advice('longer advice', 13)),
        u_state(1, 0, talk(best), 'tiny', chat((talk(best), None)),
                {**tested(0, 2), 'windows/1/window.json': {}, 'windows/1/forks/0/fork.json': {}}),
        t_state(1, 0, 'tiny', chat((talk(best), 'tiny'))),
        u_state(1, 1, talk(best, 'tiny'), 'tiny', chat((talk(best), 'tiny'), (talk(best, 'tiny'), None)), tested(1, 0)),
        t_state(1, 1, 'tiny', chat((talk(best), 'tiny'), (talk(best, 'tiny'), 'tiny'))),
        u_state(1, 2, talk(best, 'tiny', 'tiny'), 'tiny',
                chat((talk(best), 'tiny'), (talk(best, 'tiny'), 'tiny'), (talk(best, 'tiny', 'tiny'), None)), tested(1, 1)),
        t_state(1, 2, 'tiny', chat((talk(best), 'tiny'), (talk(best, 'tiny'), 'tiny'), (talk(best, 'tiny', 'tiny'), 'tiny'))),
        Done(outcome=solution, files={
            **tested(1, 2),
            'result.json': {'success': True, 'attempts': 6, 'solution': str(solution)},
        }),
    ]
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_does_not_accept_empty_replies(config, execute_run_experiment):
    world = exhausted(config, U(finish=None), 'U chat stream ended before completion')
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_preserves_the_prompt_on_provider_failure(config, execute_run_experiment):
    world = exhausted(config, U(status=400), "Error code: 400 - {'error': {'message': 'provider failed'}}")
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_records_and_uses_a_reply_with_a_lone_surrogate(config, execute_run_experiment):
    config.max_u_turns = 1
    advice = 'Use a loop �'
    world, pending = played([[(QUESTION, advice, [PASS])], [(flush(0, advice, length=12), advice, [PASS])]],
                            {advice: {'score': 12}}, config=config)
    world[0].reply = U('Use a loop \ud83d', thinking='Think.')
    world[0].logs[-1] = ('windows/0/forks/0/turns/0/u', 'text', 'Use a loop \ud83d')
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 2, pending))
    async with execute_run_experiment(config, world, u_layout=True):
        pass


async def test_resume_reuses_u_reply_written_before_turn_metadata(config, execute_run_experiment):
    config.max_u_turns = 1
    advice = 'double'
    world, pending = played([
        [(QUESTION, advice, [PASS])],
        [(flush(0, advice, length=6), advice, [PASS])],
    ], {advice: {'score': 6}}, config=config)
    transcript = 'windows/0/forks/0/u/transcript.jsonl'
    saved = ''.join(json.dumps(entry) + '\n' for entry in world[1].files.pop(transcript))
    path = config.output / transcript
    path.parent.mkdir(parents=True)
    path.write_text(saved)
    assert not (path.parent.parent / 'turns/0/metadata.json').exists()
    world[1].files.update({name: value for name, value in world[0].files.items() if name != transcript})
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 2, pending))
    # Resume goes straight to T; the only U request is in the next window.
    async with execute_run_experiment(config, world[1:], u_layout=True):
        pass
    assert path.read_text() == saved
