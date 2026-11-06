"""Real chat streaming, feedback, and incident regressions at the HTTP boundary."""

import json

import pytest

from run_one_window import run_one_window
from utils.world import U, Done, State, T

PASS = 'print(int(input()) * 2)\n'
USAGE = {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
         'prompt_tokens_details': {'cached_tokens': 50, 'cache_write_tokens': 10},
         'completion_tokens_details': {'reasoning_tokens': 20}, 'cost': 0.000123}


async def test_feeds_every_t_source_of_the_best_attempt_back(
    config, botbox_script, chat_provider, monkeypatch,
):
    from fake_botbox import FakeSession

    config.t_samples = 2
    config.max_u_turns = 2
    botbox_script.advice.extend(['long advice', 'short'])
    mutating_code = ("from pathlib import Path\nn = input()\nPath('evaluation-only.txt').write_text(n)\n"
                     "Path('helper.py').write_text('MUTATED')\nprint(int(n) * 2)\n")
    botbox_script.solutions.extend([mutating_code, PASS, PASS, PASS])
    original = FakeSession.message

    async def write_helpers(session, text):
        result = await original(session, text)
        output = session.mounts['/solution']
        (output / 'helper.py').write_text('VALUE = 42\n')
        (output / 'nested').mkdir()
        (output / 'nested/extra.py').write_text('EXTRA = 7\n')
        (output / 'binary.dat').write_bytes(b'\xff')
        (output / 'hidden.json').symlink_to((config.problem_dir / 'input_output.json'))
        return result

    monkeypatch.setattr(FakeSession, 'message', write_helpers)
    assert await run_one_window(config, on_delta=None) == config.t_dir(1, 0) / 'attempts/0/src'
    assert len(botbox_script.sessions) == 4
    feedback = chat_provider[1]['messages'][-1]['content']
    assert '/solutions/' not in feedback
    assert '<length>11 characters</length>' in feedback
    assert feedback.count('<file path="helper.py">\nVALUE = 42\n</file>') == 1
    assert '<file path="helper.py">\nMUTATED\n</file>' in feedback
    assert feedback.count('<file path="nested/extra.py">\nEXTRA = 7\n</file>') == 2
    assert mutating_code.rstrip() in feedback
    assert '<file path="evaluation-only.txt">' in feedback
    assert PASS.rstrip() in feedback
    assert 'hidden.json' not in feedback
    assert 'binary.dat' not in feedback


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


async def test_records_an_exact_role_for_an_incomplete_reply(config, botbox_script, no_retry_wait):
    botbox_script.advice.extend([{
        'deltas': [{'role': 'assistant', 'content': 'par'}, {'role': 'assistant', 'content': 'tial'}],
        'finish': 'length', 'usage': USAGE,
    }] * 9)
    with pytest.raises(RuntimeError, match='U chat'):
        await run_one_window(config, on_delta=None)
    transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    assert transcript[-1] == {'role': 'assistant', 'content': 'partial', '_complete': False}
    usage = [json.loads(line) for line in (config.u_transcripts / 'usage.jsonl').read_text().splitlines()]
    assert len(usage) == 9
    assert all(entry['usage'] == USAGE for entry in usage)


async def test_does_not_accept_empty_replies(config, botbox_script, no_retry_wait):
    botbox_script.advice.extend([{'deltas': [{'role': 'assistant'}], 'finish': None}] * 9)
    with pytest.raises(RuntimeError, match='U chat'):
        await run_one_window(config, on_delta=None)
    assert not botbox_script.sessions


async def test_preserves_the_prompt_on_provider_failure(config, botbox_script, no_retry_wait):
    botbox_script.advice.extend([{'status': 400}] * 9)
    with pytest.raises(RuntimeError, match='provider failed'):
        await run_one_window(config, on_delta=None)
    assert not botbox_script.sessions
    assert (config.problem_dir / 'question.txt').read_text() in (config.u_transcripts / 'messages.jsonl').read_text()
