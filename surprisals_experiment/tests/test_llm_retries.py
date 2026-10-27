import asyncio
import importlib
import json
from unittest.mock import AsyncMock, Mock

import httpx2
import pytest

from botbox import PiAgent
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
    {'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': None,
     'stream_error': {'code': 502, 'message': 'Provider returned error'}},
])
async def test_chat_retries_transient_calls(config, botbox_script, chat_provider, no_retry_wait, failure):
    config.u_mode = 'chat'
    botbox_script.advice.extend([failure, 'advice'])
    async with open_u_session(config) as session:
        assert await session.prompt('question') == 'advice'
        assert [m['content'] for m in session.messages if m['role'] == 'assistant'] == ['advice']
    assert len(chat_provider) == 2
    assert chat_provider[0]['messages'] == chat_provider[1]['messages']
    no_retry_wait.assert_awaited_once_with(5)
    if isinstance(failure, dict) and 'deltas' in failure:
        assert 'partial' in (config.u_transcripts / 'messages.jsonl').read_text()


@pytest.mark.parametrize('failure', [{'status': 400}, {'status': 401}, {'status': 403},
    {'deltas': [], 'finish': None, 'stream_error': {'code': 400, 'message': 'provider failed'}}])
async def test_chat_permanent_errors_fail_fast(config, botbox_script, chat_provider, no_retry_wait, failure):
    config.u_mode = 'chat'
    botbox_script.advice.extend([failure, 'unused'])
    with pytest.raises(RuntimeError, match='provider failed'):
        async with open_u_session(config) as session:
            await session.prompt('question')
    assert len(chat_provider) == 1
    no_retry_wait.assert_not_awaited()


@pytest.mark.parametrize('retries', [0, 2, 10])
async def test_chat_retry_limit(config, botbox_script, chat_provider, no_retry_wait, retries):
    config.u_mode = 'chat'
    config.llm_retries = retries
    botbox_script.advice.extend([{'status': 503}] * (retries + 1))
    with pytest.raises(RuntimeError, match='provider failed'):
        async with open_u_session(config) as session:
            await session.prompt('question')
    assert len(chat_provider) == retries + 1
    assert [c.args[0] for c in no_retry_wait.await_args_list] == [5, 10, 20, 40, 60, 60, 60, 60, 60, 60][:retries]


@pytest.mark.parametrize('agent_type', [UAgent, TAgent])
@pytest.mark.parametrize('retries', [0, 3, 10])
def test_pi_agents_share_retry_settings(monkeypatch, agent_type, retries):
    monkeypatch.setattr(PiAgent, 'stage_auth', Mock())
    kwargs = {'thinking': 'high'} if agent_type is UAgent else {'instructions': 'Do it.', 'on_delta': None}
    agent = agent_type('openrouter', 'u', api_key='unused', llm_retries=retries, **kwargs)
    home = Mock()
    agent.stage_auth(home)
    settings = json.loads(next(c.args[1] for c in home.write.call_args_list if c.args[0] == '.pi/agent/settings.json'))
    assert settings['retry'] == {
        'enabled': retries > 0, 'maxRetries': retries, 'baseDelayMs': 5000, 'maxAgentDelayMs': 60000,
    }
    assert settings['compaction']['enabled'] is (agent_type is TAgent)


async def test_cli_retry_flag(monkeypatch, tmp_path):
    cli = importlib.import_module('surprisals_experiment.cli.main')
    received = []
    async def run(config, **kwargs):
        received.append(config.llm_retries)
    monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused')
    monkeypatch.setattr(cli, 'dotenv_values', lambda *a, **kw: {'OPENROUTER_API_KEY': 'dummy'})
    monkeypatch.setattr(cli, 'run_experiment', run)
    for options in ([], ['--llm-retries', '3']):
        await cli.main(['--output', str(tmp_path / 'run'), *options, 'problem', str(tmp_path)])
    assert received == [10, 3]


async def test_retry_count_reaches_both_agent_call_sites(config, botbox_script):
    from surprisals_experiment.sdk.prompt_t import prompt_t
    config.llm_retries = 4
    async with open_u_session(config) as session:
        assert session.pi_session.agent.retry_policy.retries == 4
    botbox_script.solutions.append("print(1)")
    await prompt_t(config, 'advice', output=config.output / 'src', logs=config.output / 't')
    assert botbox_script.t_sessions[-1].agent.retry_policy.retries == 4


def test_negative_retries_are_rejected(config):
    from pydantic import ValidationError
    from surprisals_experiment.config import Config
    with pytest.raises(ValidationError):
        Config(**{**config.model_dump(), 'llm_retries': -1})
