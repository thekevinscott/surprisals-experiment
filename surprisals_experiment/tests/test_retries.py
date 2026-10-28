import asyncio
import json
from unittest.mock import AsyncMock, Mock

import httpx2
import pytest

from botbox import PiAgent
from surprisals_experiment.retry_policy import DELAYS
from surprisals_experiment.sdk.utils.u_session import open_u_session
from surprisals_experiment.sdk.utils.u_agent import UAgent
from surprisals_experiment.sdk.utils.t_agent import TAgent


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', sleep)
    return sleep


@pytest.mark.parametrize('failure', [
    {'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': None, 'drop_stream': True},
    {'status': 429}, {'status': 500}, {'status': 503},
    httpx2.ConnectError('Connection error'),
    {'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': None},
    *[{'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': None,
       'stream_error': {'code': code, 'message': 'Provider returned error'}}
      for code in (429, 500, 502, 503)],
])
async def test_chat_retries_transient_calls(config, botbox_script, chat_provider, no_retry_wait, failure):
    config.u_mode = 'chat'
    botbox_script.advice.extend([failure, 'advice'])
    async with open_u_session(config) as session:
        assert await session.prompt('question') == 'advice'
        assert [m['content'] for m in session.messages if m['role'] == 'assistant'] == ['advice']
    assert len(chat_provider) == 2
    assert chat_provider[0]['messages'] == chat_provider[1]['messages']
    no_retry_wait.assert_awaited_once_with(10)
    if isinstance(failure, dict) and 'deltas' in failure:
        assert 'partial' in (config.u_transcripts / 'messages.jsonl').read_text()


@pytest.mark.parametrize('failure', [{'status': 400}, {'status': 401}, {'status': 403},
    *[{'deltas': [], 'finish': None, 'stream_error': {'code': code, 'message': 'provider failed'}}
      for code in (400, 401, 403)]])
async def test_chat_permanent_errors_fail_fast(config, botbox_script, chat_provider, no_retry_wait, failure):
    config.u_mode = 'chat'
    botbox_script.advice.extend([failure, 'unused'])
    with pytest.raises(RuntimeError, match='provider failed'):
        async with open_u_session(config) as session:
            await session.prompt('question')
    assert len(chat_provider) == 1
    no_retry_wait.assert_not_awaited()


@pytest.mark.parametrize('dropped', [False, True], ids=['http-error', 'dropped-stream'])
async def test_chat_retry_limit(config, botbox_script, chat_provider, no_retry_wait, dropped):
    config.u_mode = 'chat'
    retries = len(DELAYS)
    failure = ({'deltas': [{'role': 'assistant', 'content': 'partial'}],
                'finish': None, 'drop_stream': True} if dropped else {'status': 503})
    botbox_script.advice.extend([failure] * (retries + 1))
    with pytest.raises(RuntimeError, match=r'U chat request failed:.*8 retries exhausted'):
        async with open_u_session(config) as session:
            await session.prompt('question')
    assert len(chat_provider) == retries + 1
    assert all(request['messages'] == chat_provider[0]['messages'] for request in chat_provider)
    if dropped:
        messages = [json.loads(line) for line in
                    (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        partials = [message['content'] for message in messages if message['role'] == 'assistant']
        assert partials == ['partial'] * (retries + 1)
        # Exhaustion retains the last partial in memory, as before this refactor.
        assert session.messages[-1]['content'] == 'partial'
    assert [c.args[0] for c in no_retry_wait.await_args_list] == list(DELAYS)
    assert sum(DELAYS) == 6520


@pytest.mark.parametrize('agent_type', [UAgent, TAgent])
def test_pi_agents_share_retry_settings(monkeypatch, agent_type):
    monkeypatch.setattr(PiAgent, 'stage_auth', Mock())
    kwargs = {'thinking': 'high'} if agent_type is UAgent else {'instructions': 'Do it.', 'on_delta': None}
    agent = agent_type('openrouter', 'u', api_key='unused', **kwargs)
    home = Mock()
    agent.stage_auth(home)
    settings = json.loads(next(c.args[1] for c in home.write.call_args_list if c.args[0] == '.pi/agent/settings.json'))
    assert settings['retry'] == {
        'enabled': True, 'maxRetries': 60, 'baseDelayMs': 5000, 'maxAgentDelayMs': 60000,
    }
    assert settings['compaction'] == (
        {'enabled': True, 'reserveTokens': 917504} if agent_type is UAgent else {'enabled': True}
    )
    if agent_type is UAgent:
        from importlib.resources import files
        model = json.loads(files('surprisals_experiment').joinpath('docker/U/models.json').read_text())
        window = model['providers']['openrouter']['models'][0]['contextWindow']
        assert window - settings['compaction']['reserveTokens'] == 131072
