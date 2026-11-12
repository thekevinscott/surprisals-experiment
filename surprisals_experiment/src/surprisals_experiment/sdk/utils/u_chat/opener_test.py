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
            (config.fork_dir / "u/transcript.jsonl").read_text().splitlines()]


async def test_streams_advice_and_appends_each_prompt(
    config, botbox_script, chat_provider,
):
    config.u_thinking = 'high'
    botbox_script.advice.extend(['first\nadvice', 'next'])
    deltas = []
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as session:
        assert await session.prompt([{'role': 'user', 'content': 'question'}], on_delta=lambda *delta: deltas.append(delta)) == 'first\nadvice'
        assert await session.prompt([{'role': 'user', 'content': 'feedback'}]) == 'next'
    assert not botbox_script.sessions
    assert chat_provider[0]['reasoning'] == {'effort': 'high'}
    assert all(request['provider'] == {'only': ['xiaomi'], 'allow_fallbacks': False} for request in chat_provider)
    assert 'tools' not in chat_provider[0]
    assert [message['role'] for message in chat_provider[1]['messages']] == ['system', 'user', 'assistant', 'user']
    assert ''.join(text for kind, text in deltas if kind == 'text') == 'first\nadvice'
    assert ('thinking', 'Thinking.') in deltas
    transcript = [json.loads(line) for line in (config.fork_dir / "u/transcript.jsonl").read_text().splitlines()]
    assert len(transcript) == 5
    assert transcript[2]['reasoning'] == 'Thinking.'
    assert transcript[-1]['content'] == 'next'
    usage = [entry for entry in transcript if entry['role'] == 'assistant']
    assert len(usage) == 2
    assert all(entry['usage'] is None for entry in usage)


async def test_cancellation_leaves_only_the_request_on_disk(config, botbox_script):
    import asyncio

    botbox_script.advice.append('advice')

    def cancel(kind, text):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as session:
            await session.prompt([{'role': 'user', 'content': 'question'}], on_delta=cancel)
    entries = transcript(config)
    assert [entry['role'] for entry in entries] == ['system', 'user']
    assert entries[-1] == {'role': 'user', 'content': 'question'}


async def test_streams_no_empty_text_alongside_reasoning(config, botbox_script):
    botbox_script.advice.append({'deltas': [
        {'role': 'assistant', 'reasoning': 'Thinking.', 'content': ''},
        {'role': 'assistant', 'reasoning': ' More.', 'content': ''},
        {'role': 'assistant', 'content': 'advice'},
    ]})
    deltas = []
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as session:
        await session.prompt([{'role': 'user', 'content': 'question'}], on_delta=lambda *delta: deltas.append(delta))
    assert deltas == [('thinking', 'Thinking.'), ('thinking', ' More.'), ('text', 'advice')]
    assert session.entries()[-1]['role'] == 'assistant'
    assert session.entries()[-1]['reasoning'] == 'Thinking. More.'


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
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as session:
        with nullcontext() if finish == 'stop' else pytest.raises(RuntimeError):
            await session.prompt([{'role': 'user', 'content': 'question'}])
        entries = transcript(config)
        assert session.entries() == entries
        if finish == 'stop':
            assert [entry['role'] for entry in entries] == ['system', 'user', 'assistant']
            assert entries[-1]['reasoning_details'] == expected
            assert entries[-1]['content'] == 'advice'
        else:
            assert [entry['role'] for entry in entries] == ['system', 'user']
            assert entries[-1] == {'role': 'user', 'content': 'question'}


@pytest.mark.parametrize('partial', [False, True])
async def test_reopened_transcript_is_the_only_history(config, botbox_script, chat_provider, partial):
    botbox_script.advice.extend(['first', 'second'])
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as live:
        await live.prompt([{'role': 'user', 'content': 'question'}], attempt=0)
    path = (config.fork_dir / "u/transcript.jsonl")
    # A change on disk must be used by the next call, without an in-memory mirror.
    text = path.read_text().replace('question', 'edited question')
    path.write_text(text)
    if partial:
        with path.open('a') as output:
            output.write('{"role": "assistant", "content":')
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as reopened:
        await reopened.prompt([{'role': 'user', 'content': 'feedback'}], attempt=1)
    assert chat_provider[-1]['messages'][1:] == [
        {'role': 'user', 'content': 'edited question'},
        {'role': 'assistant', 'content': 'first'},
        {'role': 'user', 'content': 'feedback'},
    ]
    assert transcript(config)[-1]['content'] == 'second'
    assert not any(entry.get('_reset') for entry in transcript(config))


@pytest.mark.parametrize('answered', [False, True])
async def test_reopened_pending_turn_does_not_duplicate_input(config, botbox_script, chat_provider, answered):
    botbox_script.advice.extend(['first', 'second'])
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as live:
        await live.prompt([{'role': 'user', 'content': 'question'}], attempt=0)
    path = (config.fork_dir / "u/transcript.jsonl")
    if not answered:
        path.write_text('\n'.join(path.read_text().splitlines()[:-1]) + '\n')
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as reopened:
        await reopened.prompt([{'role': 'user', 'content': 'question'}], attempt=0)
    assert chat_provider[-1]['messages'] == [
        *chat_provider[0]['messages'],
        *([{'role': 'assistant', 'content': 'first'}] if answered else []),
    ]
    assert sum(entry['role'] == 'user' for entry in transcript(config)) == 1


async def test_rebuilt_transcript_rejects_invalid_interior_line(config, chat_provider):
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as session:
        transcript = session.transcript
    with transcript.open('a') as output:
        output.write('not json\n' + json.dumps({'role': 'user', 'content': 'question', '_attempt': 0}) + '\n')
    requests = len(chat_provider)
    with pytest.raises(json.JSONDecodeError):
        async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl"):
            pass
    assert len(chat_provider) == requests


async def test_provider_error_exhaustion_leaves_the_transcript_unchanged(
    config, botbox_script, chat_provider, no_retry_wait,
):
    botbox_script.advice.extend([PROVIDER_ERROR] * (len(DELAYS) + 1))
    with pytest.raises(RuntimeError, match=r'U chat request failed:.*8 retries exhausted') as raised:
        async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as session:
            await session.prompt([{'role': 'user', 'content': 'question'}])
    assert 'U chat provider error' in str(raised.value)
    assert 'upstream failed' in str(raised.value)
    assert len(chat_provider) == len(DELAYS) + 1
    assert all(request['messages'] == chat_provider[0]['messages'] for request in chat_provider)
    assert [entry['role'] for entry in transcript(config)] == ['system', 'user']
    assert session.entries()[-1] == {'role': 'user', 'content': 'question'}
    assert no_retry_wait.await_count == len(DELAYS)


async def test_repeated_attempt_keeps_every_completed_reply_in_context(config, botbox_script, chat_provider):
    botbox_script.advice.extend(['rejected', 'accepted', 'next'])
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as session:
        await session.prompt([{'role': 'user', 'content': 'question'}], attempt=0)
        await session.prompt([{'role': 'user', 'content': 'question'}], attempt=0)
        await session.prompt([{'role': 'user', 'content': 'feedback'}], attempt=1)
    assert chat_provider[1]['messages'] == [
        *chat_provider[0]['messages'], {'role': 'assistant', 'content': 'rejected'},
    ]
    assert chat_provider[2]['messages'][1:] == [
        {'role': 'user', 'content': 'question'},
        {'role': 'assistant', 'content': 'rejected'},
        {'role': 'assistant', 'content': 'accepted'},
        {'role': 'user', 'content': 'feedback'},
    ]
    assert [entry['content'] for entry in transcript(config) if entry['role'] == 'assistant'] == ['rejected', 'accepted', 'next']
