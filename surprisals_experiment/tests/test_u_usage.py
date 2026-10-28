import json
from datetime import datetime

import pytest

from surprisals_experiment.sdk.utils.u_session import open_u_session

USAGE = {
    'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
    'prompt_tokens_details': {'cached_tokens': 50, 'cache_write_tokens': 10},
    'completion_tokens_details': {'reasoning_tokens': 20},
    'cost': 0.000123,
}


def response(text):
    return {'deltas': [{'role': 'assistant', 'content': text}], 'usage': USAGE}


@pytest.mark.parametrize('compact_chars, calls', [(0, 2), (1, 3)])
async def test_usage_preserved_separately_for_each_call(
    config, botbox_script, chat_provider, compact_chars, calls,
):
    config.u_mode = 'chat'
    config.u_compact_chars = compact_chars
    botbox_script.advice.extend(response(f'reply-{i}') for i in range(calls))
    async with open_u_session(config) as session:
        await session.prompt('question')
        await session.prompt('feedback')
    usage = [json.loads(line) for line in (config.u_transcripts / 'usage.jsonl').read_text().splitlines()]
    assert len(usage) == calls
    for entry in usage:
        assert entry['usage'] == USAGE
        assert entry['completion_id'] == 'test-chat'
        assert datetime.fromisoformat(entry['timestamp']).utcoffset().total_seconds() == 0
    messages = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    for message in messages + [m for request in chat_provider for m in request['messages']]:
        assert not ({'timestamp', 'usage', 'completion_id'} & message.keys())
    assert len([m for m in messages if m['role'] == 'assistant']) == calls


async def test_absent_usage_is_unknown_not_zero(config, botbox_script):
    config.u_mode = 'chat'
    botbox_script.advice.append('advice')
    async with open_u_session(config) as session:
        await session.prompt('question')
    usage = json.loads((config.u_transcripts / 'usage.jsonl').read_text())
    assert usage['usage'] is None


async def test_failed_call_retains_reported_usage(config, botbox_script):
    config.u_mode = 'chat'
    botbox_script.advice.extend([response('partial') | {'finish': 'length'}] * 9)
    async with open_u_session(config) as session:
        with pytest.raises(RuntimeError, match='U chat request failed'):
            await session.prompt('question')
    usage = [json.loads(line) for line in (config.u_transcripts / 'usage.jsonl').read_text().splitlines()]
    assert len(usage) == 9
    assert all(entry['usage'] == USAGE for entry in usage)


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    monkeypatch.setattr(asyncio, 'sleep', AsyncMock())
