"""Real chat streaming, feedback, and incident regressions at the HTTP boundary."""

from hashlib import sha256

from u_flush_test import PASS, QUESTION, STDOUT, chat, results
from utils.world import U, Done, State, T

USAGE = {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
         'prompt_tokens_details': {'cached_tokens': 50, 'cache_write_tokens': 10},
         'completion_tokens_details': {'reasoning_tokens': 20}, 'cost': 0.000123}
DELAYS = [10, 20, 30, 60, 180, 300, 1200, 1800]
MUTATING = ("from pathlib import Path\nn = input()\nPath('evaluation-only.txt').write_text(n)\n"
            "Path('helper.py').write_text('MUTATED')\nprint(int(n) * 2)\n")


def prompt(index, advice, *samples):
    code = '\n'.join(f'<T-{sample}>\n' + ''.join(f'<file path="{path}">\n{text.rstrip()}\n</file>\n'
                                                 for path, text in files.items()) + f'</T-{sample}>'
                     for sample, files in enumerate(samples))
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>{index}</index>\n'
            f'<length>{len(advice)} characters</length>\n<advice>\n{advice}\n</advice>\n'
            f'<code>\n{code}\n</code>\n</attempt>')


def exhausted(reply, error, *, recorded=None, usage=None, completion_id='u'):
    """U's first try and all 8 retries fail with `error`."""
    def messages(tries):
        return [*chat(0, (QUESTION, None))['u/transcripts/messages.jsonl'], *[recorded] * tries]

    def files(tries):
        row = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': completion_id, 'usage': usage}
        return {'u/transcripts/usage.jsonl': [row] * tries,
                **({'u/transcripts/messages.jsonl': messages(tries)} if recorded else {})}

    sent = {'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
            'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': QUESTION}]}
    u = 'windows/0/forks/0/turns/0/u'
    text = [(u, 'text', reply.text)] if reply.text else []
    first = {'settings.json': ..., 'windows/0/window.json': {}, 'windows/0/forks/0/fork.json': {},
             'u/transcripts/messages.jsonl': messages(0)}
    return [State(reply, sent=sent, logs=text, files=first),
            *(State(reply, sent=sent, logs=[(u, 'retry', f'{tries}/8 in {delay}s: {error}\n'), *text],
                    files=files(tries)) for tries, delay in enumerate(DELAYS, 1)),
            Done(outcome=RuntimeError(f'U chat request failed: {error}; 8 retries exhausted'), files=files(9))]


async def test_feeds_every_t_source_of_the_best_attempt_back(config, execute_run_experiment):
    config.t_samples = 2
    config.max_u_turns = 2
    io = config.problem_dir / 'input_output.json'
    helpers = {'helper.py': 'VALUE = 42\n', 'nested/extra.py': 'EXTRA = 7\n', 'binary.dat': b'\xff', 'hidden.json': io}
    mutated = {'evaluation-only.txt': '7', 'helper.py': 'MUTATED', 'main.py': MUTATING,
               'nested/extra.py': 'EXTRA = 7\n'}
    clean = {'helper.py': 'VALUE = 42\n', 'main.py': PASS, 'nested/extra.py': 'EXTRA = 7\n'}
    first = prompt(0, 'long advice', mutated, clean)
    best = prompt(1, 'short', clean, clean)

    def turn(window, number):
        return f'windows/{window}/forks/0/turns/{number}'

    def u(window, number, user, advice, files):
        path = f'{turn(window, number)}/u'
        return State(U(advice, thinking='Think.'),
                     sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                           'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user}]},
                     logs=[(path, 'thinking', 'Think.'), (path, 'text', advice)], files=files)

    def t(window, number, sample, advice, code, files=None):
        ts = f'{turn(window, number)}/ts/{sample}'
        src = {**helpers, 'main.py': code, 'hidden.json': io.read_text()}
        return State(T({'main.py': code, **helpers}, thinking='Write main.py.', text='Done.'),
                     sent=(f'{ts}/attempts/0', advice),
                     logs=[(ts, 'thinking', 'Write main.py.'), (ts, 'text', 'Done.')],
                     files={**(files or {}), f'{ts}/attempts/0/stdout.txt': STDOUT,
                            **{f'{ts}/attempts/0/src/{name}': text for name, text in src.items()}})

    def advised(window, number, advice, score=None):
        digest = f'advices/{sha256(advice.encode()).hexdigest()}'
        path = turn(window, number)
        files = {f'{path}/metadata.json': {'advice': digest}, f'{path}/u/advice.txt': advice}
        return files | ({f'{digest}/advice.txt': advice, f'{digest}/advice.json': {'score': score}} if score else {})

    def evaluated(window, number):
        return {path: content for sample in range(2)
                for path, content in results(f'{turn(window, number)}/ts/{sample}/attempts/0', PASS).items()}

    def opened(window):
        return {f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}

    solution = config.output / turn(0, 1) / 'ts/0/attempts/0/src'
    world = [
        u(0, 0, QUESTION, 'long advice', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t(0, 0, 0, 'long advice', MUTATING, {**chat(0, (QUESTION, 'long advice')), **advised(0, 0, 'long advice', 11)}),
        t(0, 0, 1, 'long advice', PASS),
        u(0, 1, first, 'short', {**evaluated(0, 0), **chat(0, (QUESTION, 'long advice'), (first, None)),
                                 f'{turn(0, 0)}/ts/0/attempts/0/src/evaluation-only.txt': '7',
                                 f'{turn(0, 0)}/ts/0/attempts/0/src/helper.py': 'MUTATED'}),
        t(0, 1, 0, 'short', PASS, {**chat(0, (QUESTION, 'long advice'), (first, 'short')),
                                   **advised(0, 1, 'short', 5)}),
        t(0, 1, 1, 'short', PASS),
        u(1, 0, best, 'short', {**evaluated(0, 1), **opened(1), **chat(1, (best, None))}),
        t(1, 0, 0, 'short', PASS, {**chat(1, (best, 'short')), **advised(1, 0, 'short')}),
        t(1, 0, 1, 'short', PASS),
        u(1, 1, best, 'short', {**evaluated(1, 0), **chat(1, (best, 'short'), (best, None))}),
        t(1, 1, 0, 'short', PASS, {**chat(1, (best, 'short'), (best, 'short')), **advised(1, 1, 'short')}),
        t(1, 1, 1, 'short', PASS),
        Done(outcome=solution, files={**evaluated(1, 1),
                                      'result.json': {'success': True, 'attempts': 4, 'solution': str(solution)}}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_sends_and_records_exact_roles(config, execute_run_experiment):
    config.max_u_turns = 3
    question = 'Read an integer and print its double.'
    best = ('<original_question>\nRead an integer and print its double.\n</original_question>\n\n'
            '<attempt>\n<index>0</index>\n<length>4 characters</length>\n<advice>\ntiny\n</advice>\n'
            '<code>\n<T-0>\n<file path="main.py">\nprint(int(input()) * 2)\n</file>\n</T-0>\n</code>\n</attempt>')
    advices = {'tiny': 'advices/8950abfda7b727630760dd35bcf5c3daa7631aff223a90f7728c0d2521dde10c',
               'long advice': 'advices/9cca26ad57d22afe3fb910db6323538932cd68c68ca666f6c97b03ca76f188ab',
               'longer advice': 'advices/6c5930dfdad8282d9030e1cd507d78acfc26231d4fc74758d85584199ee9f561'}
    system = {'role': 'system', 'content': ...}
    usage = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
    tests = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
        {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
        {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
    ]}
    stdout = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write it."}}\n'
              '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')

    def chat(*turns):
        messages = [system]
        for user, advice in turns:
            messages += [system, {'role': 'user', 'content': user, '_reset': True}]
            if advice:
                messages.append({'role': 'assistant', 'content': advice, 'reasoning': 'Think.', '_complete': True})
        return messages

    def transcripts(window):
        return 'u/transcripts' if window == 0 else f'windows/{window}/forks/0/u/transcripts'

    def tested(window, turn):
        return {f'windows/{window}/forks/0/turns/{turn}/ts/0/attempts/0/generation.json': {'exit_code': 0},
                f'windows/{window}/forks/0/turns/{turn}/ts/0/attempts/0/tests.json': tests}

    def u_state(window, turn, user, advice, messages, files):
        return State(
            U(advice, thinking='Think.'),
            sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                  'messages': [system, {'role': 'user', 'content': user}]},
            logs=[(f'windows/{window}/forks/0/turns/{turn}/u', 'thinking', 'Think.'),
                  (f'windows/{window}/forks/0/turns/{turn}/u', 'text', advice)],
            files={f'{transcripts(window)}/messages.jsonl': messages, **files},
        )

    def t_state(window, turn, advice, messages, files=None):
        t = f'windows/{window}/forks/0/turns/{turn}'
        return State(
            T({'main.py': PASS}, thinking='Write it.', text='Done.'),
            sent=(f'{t}/ts/0/attempts/0', advice),
            logs=[(f'{t}/ts/0', 'thinking', 'Write it.'), (f'{t}/ts/0', 'text', 'Done.')],
            files={
                f'{transcripts(window)}/messages.jsonl': messages,
                f'{transcripts(window)}/usage.jsonl': [usage] * (turn + 1),
                f'{t}/metadata.json': {'advice': advices[advice]},
                f'{t}/u/advice.txt': advice,
                f'{t}/ts/0/attempts/0/stdout.txt': stdout,
                f'{t}/ts/0/attempts/0/src/main.py': PASS,
                **(files or {}),
            },
        )

    def new_advice(advice, score):
        return {f'{advices[advice]}/advice.txt': advice, f'{advices[advice]}/advice.json': {'score': score}}

    solution = config.output / 'windows/0/forks/0/turns/0/ts/0/attempts/0/src'
    world = [
        u_state(0, 0, question, 'tiny', chat((question, None)), {
            'settings.json': {
                'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
                'u_thinking': 'high', 't_model': 't', 'cap_strategy': 'characters', 'scorer_base_url': None,
                't_samples': 1, 't_pool_size': 3, 't_sample_timeout': 900.0, 't_sample_retries': 3,
                'window_forks': 1, 'fork_turns': 10, 'window_solo_turns': 30, 'max_u_turns': 3,
                'git_commit': ...,
            },
            'windows/0/window.json': {},
            'windows/0/forks/0/fork.json': {},
        }),
        t_state(0, 0, 'tiny', chat((question, 'tiny')), new_advice('tiny', 4)),
        u_state(0, 1, best, 'long advice', chat((question, 'tiny'), (best, None)), tested(0, 0)),
        t_state(0, 1, 'long advice', chat((question, 'tiny'), (best, 'long advice')), new_advice('long advice', 11)),
        u_state(0, 2, best, 'longer advice', chat((question, 'tiny'), (best, 'long advice'), (best, None)),
                tested(0, 1)),
        t_state(0, 2, 'longer advice', chat((question, 'tiny'), (best, 'long advice'), (best, 'longer advice')),
                new_advice('longer advice', 13)),
        u_state(1, 0, best, 'tiny', chat((best, None)),
                {**tested(0, 2), 'windows/1/window.json': {}, 'windows/1/forks/0/fork.json': {}}),
        t_state(1, 0, 'tiny', chat((best, 'tiny'))),
        u_state(1, 1, best, 'tiny', chat((best, 'tiny'), (best, None)), tested(1, 0)),
        t_state(1, 1, 'tiny', chat((best, 'tiny'), (best, 'tiny'))),
        u_state(1, 2, best, 'tiny', chat((best, 'tiny'), (best, 'tiny'), (best, None)), tested(1, 1)),
        t_state(1, 2, 'tiny', chat((best, 'tiny'), (best, 'tiny'), (best, 'tiny'))),
        Done(outcome=solution, files={
            **tested(1, 2),
            'result.json': {'success': True, 'attempts': 6, 'solution': str(solution)},
        }),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_records_an_exact_role_for_an_incomplete_reply(config, execute_run_experiment):
    world = exhausted(U('partial', finish='length', usage=USAGE),
                      'U hit its output token limit (30 completion tokens, 20 reasoning tokens)',
                      recorded={'role': 'assistant', 'content': 'partial', '_complete': False}, usage=USAGE)
    async with execute_run_experiment(config, world):
        pass


async def test_does_not_accept_empty_replies(config, execute_run_experiment):
    world = exhausted(U(finish=None), 'U chat stream ended before completion',
                      recorded={'role': 'assistant', '_complete': False})
    async with execute_run_experiment(config, world):
        pass


async def test_preserves_the_prompt_on_provider_failure(config, execute_run_experiment):
    world = exhausted(U(status=400), "Error code: 400 - {'error': {'message': 'provider failed'}}", completion_id=None)
    async with execute_run_experiment(config, world):
        pass
