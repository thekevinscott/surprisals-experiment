import json
from contextlib import nullcontext

import pytest

from surprisals_experiment.retry_policy.constants import DELAYS
from surprisals_experiment.sdk.utils.u_chat import open_u_chat

PROVIDER_ERROR = {
    'deltas': [{'role': 'assistant', 'content': 'partial', 'reasoning': 'partial reasoning'}],
    'finish': 'error', 'finish_choice': {'error': {'message': 'upstream failed', 'code': 502}},
}


def transcript(config, name="messages.jsonl"):
    return [json.loads(line) for line in
            (config.u_transcripts / name).read_text().splitlines()]


async def test_streams_advice_and_extends_each_prompt(
    config, botbox_script, chat_provider,
):
    config.u_thinking = 'high'
    botbox_script.advice.extend(['first\nadvice', 'next'])
    deltas = []
    async with open_u_chat(config) as session:
        assert await session.prompt([{'role': 'user', 'content': 'question'}], on_delta=lambda *delta: deltas.append(delta)) == 'first\nadvice'
        assert await session.prompt([*session.messages, {'role': 'user', 'content': 'feedback'}]) == 'next'
    assert not botbox_script.sessions
    assert chat_provider[0]['reasoning'] == {'effort': 'high'}
    assert all(request['provider'] == {'only': ['xiaomi'], 'allow_fallbacks': False} for request in chat_provider)
    assert 'tools' not in chat_provider[0]
    assert [message['role'] for message in chat_provider[1]['messages']] == ['user', 'assistant', 'user']
    assert ''.join(text for kind, text in deltas if kind == 'text') == 'first\nadvice'
    assert ('thinking', 'Thinking.') in deltas
    transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    assert len(transcript) == 4
    assert transcript[1] == {'role': 'assistant', 'content': 'first\nadvice'}
    replies = [json.loads(line) for line in (config.u_transcripts / 'replies.jsonl').read_text().splitlines()]
    assert [entry['message']['reasoning'] for entry in replies] == ['Thinking.', 'Thinking.']
    assert transcript[-1]['content'] == 'next'
    usage = [json.loads(line) for line in (config.u_transcripts / 'usage.jsonl').read_text().splitlines()]
    assert len(usage) == 2
    assert all(entry['usage'] is None for entry in usage)


async def test_saves_partial_output_on_cancellation(config, botbox_script):
    import asyncio

    botbox_script.advice.append('advice')

    def cancel(kind, text):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        async with open_u_chat(config) as session:
            await session.prompt([{'role': 'user', 'content': 'question'}], on_delta=cancel)
    transcript = (config.u_transcripts / 'messages.jsonl').read_text()
    assert json.loads(transcript) == {'role': 'user', 'content': 'question'}
    replies = [json.loads(line) for line in (config.u_transcripts / 'replies.jsonl').read_text().splitlines()]
    assert replies[-1]['message']['reasoning'] == 'Thinking.'


async def test_streams_no_empty_text_alongside_reasoning(config, botbox_script):
    botbox_script.advice.append({'deltas': [
        {'role': 'assistant', 'reasoning': 'Thinking.', 'content': ''},
        {'role': 'assistant', 'reasoning': ' More.', 'content': ''},
        {'role': 'assistant', 'content': 'advice'},
    ]})
    deltas = []
    async with open_u_chat(config) as session:
        await session.prompt([{'role': 'user', 'content': 'question'}], on_delta=lambda *delta: deltas.append(delta))
    assert deltas == [('thinking', 'Thinking.'), ('thinking', ' More.'), ('text', 'advice')]
    assert session.messages[-1]['role'] == 'assistant'
    assert session.messages[-1] == {'role': 'assistant', 'content': 'advice'}
    assert transcript(config, 'replies.jsonl')[-1]['message']['reasoning'] == 'Thinking. More.'


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
            await session.prompt([{'role': 'user', 'content': 'question'}])
        replies = transcript(config, 'replies.jsonl')
        assert len(replies) == (1 if finish == 'stop' else 9)
        assert all(entry['message']['reasoning_details'] == expected for entry in replies)
        assert all(entry['message']['content'] == 'advice' for entry in replies)
        assert session.messages == [{'role': 'user', 'content': 'question'}] + (
            [{'role': 'assistant', 'content': 'advice'}] if finish == 'stop' else [])


@pytest.mark.parametrize('mode', ['plain', 'partial'])
async def test_rebuilt_transcript_matches_live_session(
    config, botbox_script, chat_provider, no_retry_wait, mode,
):
    replies = ['first']
    if mode == 'partial':
        replies.append({'deltas': [{'role': 'assistant', 'content': 'unfinished'}],
                        'finish': 'content_filter'})
    replies.append('second')
    botbox_script.advice.extend(replies)
    async with open_u_chat(config) as live:
        assert await live.prompt([{'role': 'user', 'content': 'question'}]) == 'first'
        request = [*live.messages, {'role': 'user', 'content': 'feedback'}]
        assert await live.prompt(request) == 'second'
        expected = list(live.messages)
    transcript = config.u_transcripts / 'messages.jsonl'
    entries = [json.loads(line) for line in transcript.read_text().splitlines()]
    assert entries == expected
    assert len(live.messages) == 4
    before_replay = transcript.read_bytes()
    before_inode = transcript.stat().st_ino
    if mode == 'partial':
        replies = [json.loads(line) for line in (config.u_transcripts / 'replies.jsonl').read_text().splitlines()]
        assert [entry['message']['content'] for entry in replies] == ['first', 'unfinished', 'second']
        assert all(message.get('content') != 'unfinished' for message in live.messages)
        # A process can stop midway through the next appended transcript entry.
        with transcript.open('a') as output:
            output.write('{"role": "assistant", "content":')
    requests = len(chat_provider)
    async with open_u_chat(config) as rebuilt:
        assert rebuilt.messages == expected
        assert await rebuilt.prompt(request) == 'second'
    assert len(chat_provider) == requests
    assert transcript.read_bytes() == before_replay
    if mode == 'partial':
        assert transcript.stat().st_ino != before_inode
        botbox_script.advice.append('third')
        async with open_u_chat(config) as resumed:
            assert await resumed.prompt([*resumed.messages, {'role': 'user', 'content': 'next feedback'}]) == 'third'
        async with open_u_chat(config) as rebuilt:
            assert rebuilt.messages == resumed.messages
            assert rebuilt.messages[-1] == {'role': 'assistant', 'content': 'third'}


async def test_rebuilt_transcript_resumes_pending_turn(config, botbox_script, chat_provider):
    botbox_script.advice.extend(['first', 'second'])
    async with open_u_chat(config) as live:
        assert await live.prompt([{'role': 'user', 'content': 'question'}]) == 'first'
        request = [*live.messages, {'role': 'user', 'content': 'feedback'}]
        assert await live.prompt(request) == 'second'
    transcript = config.u_transcripts / 'messages.jsonl'
    entries = [json.loads(line) for line in transcript.read_text().splitlines()]
    end = len(request)
    transcript.write_text(''.join(json.dumps(entry) + '\n' for entry in entries[:end]))
    botbox_script.advice.append('second')
    requests = len(chat_provider)
    async with open_u_chat(config) as rebuilt:
        assert await rebuilt.prompt(request) == 'second'
        assert rebuilt.messages == live.messages
        assert rebuilt.messages[-1] == {'role': 'assistant', 'content': 'second'}
    assert len(chat_provider) - requests == 1
    restored = [json.loads(line) for line in transcript.read_text().splitlines()]
    assert restored == [*request, {'role': 'assistant', 'content': 'second'}]


async def test_rebuilt_transcript_rejects_invalid_interior_line(config, chat_provider):
    async with open_u_chat(config) as session:
        transcript = session.transcript
    transcript.parent.mkdir(parents=True, exist_ok=True)
    with transcript.open('a') as output:
        output.write('not json\n' + json.dumps({'role': 'user', 'content': 'question'}) + '\n')
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
            await session.prompt([{'role': 'user', 'content': 'question'}])
    assert 'U chat provider error' in str(raised.value)
    assert 'upstream failed' in str(raised.value)
    assert len(chat_provider) == len(DELAYS) + 1
    assert all(request['messages'] == chat_provider[0]['messages'] for request in chat_provider)
    assert transcript(config) == session.messages == [{'role': 'user', 'content': 'question'}]
    replies = transcript(config, 'replies.jsonl')
    assert [entry['message']['content'] for entry in replies] == ['partial'] * 9
    assert all('provider_error' in entry['message'] for entry in replies)
    assert no_retry_wait.await_count == len(DELAYS)
