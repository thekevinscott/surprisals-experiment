import json
from contextlib import nullcontext

import pytest

from surprisals_experiment.retry_policy.constants import DELAYS
from surprisals_experiment.sdk.utils.u_chat import open_u_chat

PROVIDER_ERROR = {
    'deltas': [{'role': 'assistant', 'content': 'partial', 'reasoning': 'partial reasoning'}],
    'finish': 'error', 'finish_choice': {'error': {'message': 'upstream failed', 'code': 502}},
}


def transcript(config):
    return [json.loads(line) for line in
            (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]


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
    assert 'max_tokens' not in chat_provider[0]
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


async def test_caps_u_output_tokens_when_set(config, botbox_script, chat_provider):
    config.u_max_tokens = 4096
    botbox_script.advice.append('advice')
    async with open_u_chat(config) as session:
        await session.prompt('question')
    assert chat_provider[0]['max_tokens'] == 4096
    assert chat_provider[0]['reasoning'] == {'effort': 'high'}


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


async def test_provider_error_exhaustion_preserves_partial_evidence(
    config, botbox_script, chat_provider, no_retry_wait,
):
    botbox_script.advice.extend([PROVIDER_ERROR] * (len(DELAYS) + 1))
    with pytest.raises(RuntimeError, match=r'U chat request failed:.*8 retries exhausted') as raised:
        async with open_u_chat(config) as session:
            await session.prompt('question')
    assert 'U chat provider error' in str(raised.value)
    assert 'upstream failed' in str(raised.value)
    assert len(chat_provider) == len(DELAYS) + 1
    assert all(request['messages'] == chat_provider[0]['messages'] for request in chat_provider)
    assert [m['content'] for m in transcript(config) if m['role'] == 'assistant'] == ['partial'] * 9
    assert session.messages[-1]['content'] == 'partial'
    assert no_retry_wait.await_count == len(DELAYS)
