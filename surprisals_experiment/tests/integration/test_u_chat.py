"""Real chat streaming, feedback, and incident regressions at the HTTP boundary."""

import json
from contextlib import nullcontext

import pytest

from run_one_window import run_one_window
from surprisals_experiment.sdk.utils.u_chat import open_u_chat
from utils.world import U, Done, State, T

PASS = 'print(int(input()) * 2)\n'
USAGE = {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
         'prompt_tokens_details': {'cached_tokens': 50, 'cache_write_tokens': 10},
         'completion_tokens_details': {'reasoning_tokens': 20}, 'cost': 0.000123}


async def test_streams_advice_and_starts_each_prompt_fresh(
    config, botbox_script, chat_provider,
):
    config.u_thinking = 'high'
    botbox_script.advice.extend(['first\nadvice', 'next'])
    deltas = []
    async with open_u_chat(config) as session:
        assert await session.prompt('question', on_delta=lambda *delta: deltas.append(delta)) == 'first\nadvice'
        assert await session.prompt('feedback') == 'next'
    assert not botbox_script.sessions
    assert chat_provider[0]['reasoning'] == {'effort': 'high'}
    assert 'tools' not in chat_provider[0]
    assert [message['role'] for message in chat_provider[1]['messages']] == ['system', 'user']
    assert ''.join(text for kind, text in deltas if kind == 'text') == 'first\nadvice'
    assert ('thinking', 'Thinking.') in deltas
    transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    assert len(transcript) == 5
    assert transcript[2]['reasoning'] == 'Thinking.'
    assert transcript[-1]['content'] == 'next'
    usage = [json.loads(line) for line in (config.u_transcripts / 'usage.jsonl').read_text().splitlines()]
    assert len(usage) == 2
    assert all(entry['usage'] is None for entry in usage)


async def test_feeds_every_t_source_of_the_best_attempt_back(
    config, botbox_script, chat_provider, monkeypatch,
):
    from conftest import FakeSession

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
    assert await run_one_window(config, on_delta=None) == config.t_dir(1, 0) / 'src'
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
        return {f'windows/{window}/forks/0/turns/{turn}/ts/0/generation.json': {'exit_code': 0},
                f'windows/{window}/forks/0/turns/{turn}/ts/0/tests.json': tests}

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
            sent=(f'{t}/ts/0', advice),
            logs=[(f'{t}/ts/0', 'thinking', 'Write it.'), (f'{t}/ts/0', 'text', 'Done.')],
            files={
                f'{transcripts(window)}/messages.jsonl': messages,
                f'{transcripts(window)}/usage.jsonl': [usage] * (turn + 1),
                f'{t}/metadata.json': {'advice': advices[advice]},
                f'{t}/u/advice.txt': advice,
                f'{t}/ts/0/stdout.txt': stdout,
                f'{t}/ts/0/src/main.py': PASS,
                **(files or {}),
            },
        )

    def new_advice(advice, score):
        return {f'{advices[advice]}/advice.txt': advice, f'{advices[advice]}/advice.json': {'score': score}}

    solution = config.output / 'windows/0/forks/0/turns/0/ts/0/src'
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


async def test_saves_partial_output_on_cancellation(config, botbox_script):
    import asyncio

    botbox_script.advice.append('advice')

    def cancel(kind, text):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        async with open_u_chat(config) as session:
            await session.prompt('question', on_delta=cancel)
    transcript = (config.u_transcripts / 'messages.jsonl').read_text()
    assert 'Thinking.' in transcript


async def test_streams_no_empty_text_alongside_reasoning(config, botbox_script):
    botbox_script.advice.append({'deltas': [
        {'role': 'assistant', 'reasoning': 'Thinking.', 'content': ''},
        {'role': 'assistant', 'reasoning': ' More.', 'content': ''},
        {'role': 'assistant', 'content': 'advice'},
    ]})
    deltas = []
    async with open_u_chat(config) as session:
        await session.prompt('question', on_delta=lambda *delta: deltas.append(delta))
    assert deltas == [('thinking', 'Thinking.'), ('thinking', ' More.'), ('text', 'advice')]
    assert session.messages[-1]['role'] == 'assistant'
    assert session.messages[-1]['reasoning'] == 'Thinking. More.'


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


@pytest.mark.parametrize('finish', ['stop', None])
async def test_reasoning_format_preserves_latest_provider_value(
    config, botbox_script, finish, no_retry_wait,
):
    final_format = 'provider.v1'
    reply = {
        'deltas': [
            {'role': 'assistant', 'reasoning_details': [
                {'type': 'reasoning.text', 'index': 0, 'text': 'Think', 'format': 'unknown'},
                {'type': 'reasoning.text', 'index': 1, 'text': 'Other', 'format': 'other'},
            ]},
            {'reasoning_details': [
                {'type': 'reasoning.text', 'index': 1, 'text': ' thought', 'format': 'other'},
                {'type': 'reasoning.text', 'index': 0, 'text': ' more', 'format': final_format},
            ]},
            {'reasoning_details': [{'type': 'reasoning.text', 'index': 0, 'text': '.'}],
             'content': 'advice'},
        ], 'finish': finish,
    }
    botbox_script.advice.extend([reply] * (1 if finish == 'stop' else 9))
    expected = [
        {'type': 'reasoning.text', 'index': 0, 'text': 'Think more.', 'format': final_format},
        {'type': 'reasoning.text', 'index': 1, 'text': 'Other thought', 'format': 'other'},
    ]
    async with open_u_chat(config) as session:
        with nullcontext() if finish == 'stop' else pytest.raises(RuntimeError):
            await session.prompt('question')
        assert session.messages[-1]['reasoning_details'] == expected
        transcript = [json.loads(line) for line in session.transcript.read_text().splitlines()]
        assert transcript[-1]['reasoning_details'] == expected
        assert transcript[-1]['content'] == 'advice'


@pytest.mark.parametrize('mode', ['plain', 'partial'])
async def test_rebuilt_transcript_matches_live_session(
    config, botbox_script, chat_provider, no_retry_wait, mode,
):
    replies = ['first']
    if mode == 'partial':
        replies.append({'deltas': [{'role': 'assistant', 'content': 'unfinished'}],
                        'finish': 'length'})
    replies.append('second')
    botbox_script.advice.extend(replies)
    async with open_u_chat(config) as live:
        live.attempt = 0
        assert await live.prompt('question') == 'first'
        live.attempt = 1
        assert await live.prompt('feedback') == 'second'
        expected = (live.messages, live.turn_attempt, live.turn_reply)
    transcript = config.u_transcripts / 'messages.jsonl'
    entries = [json.loads(line) for line in transcript.read_text().splitlines()]
    if mode == 'plain':
        assert entries[-2]['_reset'] is True
    assert len(live.messages) == 3
    before_replay = transcript.read_bytes()
    before_inode = transcript.stat().st_ino
    if mode == 'partial':
        assert any(entry.get('_complete') is False for entry in entries)
        assert all(message.get('content') != 'unfinished' for message in live.messages)
        # A process can stop midway through the next appended transcript entry.
        with transcript.open('a') as output:
            output.write('{"role": "assistant", "content":')
    requests = len(chat_provider)
    async with open_u_chat(config) as rebuilt:
        assert (rebuilt.messages, rebuilt.turn_attempt, rebuilt.turn_reply) == expected
        rebuilt.attempt = 1
        assert await rebuilt.prompt('feedback') == 'second'
    assert len(chat_provider) == requests
    assert transcript.read_bytes() == before_replay
    if mode == 'partial':
        assert transcript.stat().st_ino != before_inode
        botbox_script.advice.append('third')
        async with open_u_chat(config) as resumed:
            resumed.attempt = 2
            assert await resumed.prompt('next feedback') == 'third'
        async with open_u_chat(config) as rebuilt:
            assert rebuilt.messages == resumed.messages
            assert rebuilt.turn_attempt == 2
            assert rebuilt.turn_reply == 'third'


async def test_rebuilt_transcript_resumes_pending_turn(config, botbox_script, chat_provider):
    botbox_script.advice.extend(['first', 'second'])
    async with open_u_chat(config) as live:
        live.attempt = 0
        assert await live.prompt('question') == 'first'
        live.attempt = 1
        assert await live.prompt('feedback') == 'second'
    transcript = config.u_transcripts / 'messages.jsonl'
    entries = [json.loads(line) for line in transcript.read_text().splitlines()]
    end = next(i for i, entry in enumerate(entries) if entry.get('_attempt') == 1) + 1
    transcript.write_text(''.join(json.dumps(entry) + '\n' for entry in entries[:end]))
    botbox_script.advice.append('second')
    requests = len(chat_provider)
    async with open_u_chat(config) as rebuilt:
        rebuilt.attempt = 1
        assert await rebuilt.prompt('feedback') == 'second'
        assert rebuilt.messages == live.messages
        assert rebuilt.turn_attempt == 1
        assert rebuilt.turn_reply == 'second'
    assert len(chat_provider) - requests == 1
    restored = [json.loads(line) for line in transcript.read_text().splitlines()]
    assert sum(entry.get('_attempt') == 1 for entry in restored) == 1


async def test_rebuilt_transcript_rejects_invalid_interior_line(config, chat_provider):
    async with open_u_chat(config) as session:
        transcript = session.transcript
    with transcript.open('a') as output:
        output.write('not json\n' + json.dumps({'role': 'user', 'content': 'question', '_attempt': 0}) + '\n')
    requests = len(chat_provider)
    with pytest.raises(json.JSONDecodeError):
        async with open_u_chat(config):
            pass
    assert len(chat_provider) == requests
