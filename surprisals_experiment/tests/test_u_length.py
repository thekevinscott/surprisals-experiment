import asyncio
import importlib
from unittest.mock import AsyncMock

import pytest

from surprisals_experiment.sdk.utils.u_session import open_u_session
from surprisals_experiment.sdk.utils.u_session.advice_from_events import advice_from_events
from surprisals_experiment.sdk.utils.u_session.u_session_error import USessionError


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', sleep)
    return sleep


def length_reply(tokens=None):
    reply = {'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': 'length'}
    if tokens is not None:
        reply['usage'] = {'prompt_tokens': 10, 'completion_tokens': tokens, 'total_tokens': tokens + 10,
                          'completion_tokens_details': {'reasoning_tokens': tokens - 1}}
    return reply


def describe_chat_length_stop():
    @pytest.mark.parametrize("raw_finish", [False, True], ids=["sdk-length-error", "length-finish-reason"])
    async def it_retries_original_request_and_preserves_partial_transcript(config, botbox_script, chat_provider, no_retry_wait, monkeypatch, raw_finish):
        if raw_finish:
            from openai.lib.streaming.chat import AsyncChatCompletionStream
            async def final(stream):
                return stream.current_completion_snapshot
            monkeypatch.setattr(AsyncChatCompletionStream, "get_final_completion", final)
        config.u_mode = 'chat'
        botbox_script.advice.extend([length_reply(20), 'good advice'])
        async with open_u_session(config) as session:
            assert await session.prompt('question') == 'good advice'
            assert [m['content'] for m in session.messages if m['role'] == 'assistant'] == ['good advice']
        assert chat_provider[0]['messages'] == chat_provider[1]['messages']
        assert 'partial' in (config.u_transcripts / 'messages.jsonl').read_text()
        no_retry_wait.assert_awaited_once_with(10)

    @pytest.mark.parametrize('counts', [True, False, 'missing-last'])
    async def it_exhausts_with_clear_final_stderr(config, botbox_script, chat_provider, monkeypatch, capsys, no_retry_wait, counts):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *a, **kw: {'OPENROUTER_API_KEY': 'dummy'})
        botbox_script.advice.extend(length_reply(20 + i if counts and not (counts == 'missing-last' and i == 8) else None) for i in range(9))
        with pytest.raises(SystemExit) as caught:
            await cli.main(['--output', str(config.output), 'problem', str(config.problem_dir), '--u-mode', 'chat'])
        assert caught.value.code == 2
        last = capsys.readouterr().err.splitlines()[-1]
        assert 'U hit its output token limit' in last
        assert '8 retries exhausted' in last
        if counts is True:
            assert '28 completion tokens' in last
            assert '27 reasoning tokens' in last
        else:
            assert 'completion tokens' not in last
            assert 'reasoning tokens' not in last
        assert len(chat_provider) == 9
        assert [c.args[0] for c in no_retry_wait.await_args_list] == [10,20,30,60,180,300,1200,1800]
        assert not botbox_script.t_sessions


def describe_agent_length_stop():
    @pytest.mark.parametrize('usage, expected', [(None, ''), ({'output': 131072}, '131072 completion tokens'),
        ({'output': 0}, '0 completion tokens')])
    @pytest.mark.parametrize('text', ['', 'partial advice'])
    def it_reports_limit_even_with_partial_advice(usage, expected, text):
        message = {'role': 'assistant', 'stopReason': 'length', 'content': [{'type': 'text', 'text': text}]}
        if usage is not None:
            message['usage'] = usage
        events = [{'type': 'agent_end', 'messages': [message]}, {'type': 'agent_settled'}]
        with pytest.raises(USessionError, match='U hit its output token limit') as caught:
            advice_from_events(events)
        assert expected in str(caught.value)
        assert 'retries exhausted' not in str(caught.value)
        assert 'reasoning tokens' not in str(caught.value)
        if usage is None:
            assert 'completion tokens' not in str(caught.value)

@pytest.mark.parametrize('reasoning', [0, 131071])
def test_agent_reports_available_reasoning_count(reasoning):
    events = [{'type': 'agent_end', 'messages': [{'role': 'assistant', 'stopReason': 'length',
        'content': [], 'usage': {'output': 131072, 'reasoning': reasoning}}]}, {'type': 'agent_settled'}]
    with pytest.raises(USessionError) as caught:
        advice_from_events(events)
    assert '131072 completion tokens' in str(caught.value)
    assert f'{reasoning} reasoning tokens' in str(caught.value)

async def test_length_and_http_errors_share_one_budget(config, botbox_script, chat_provider, no_retry_wait):
    config.u_mode = 'chat'
    botbox_script.advice.extend([{'status': 503}, length_reply()] * 4 + [length_reply(100)])
    async with open_u_session(config) as session:
        with pytest.raises(RuntimeError, match=r'U hit its output token limit.*100 completion tokens.*8 retries exhausted'):
            await session.prompt('question')
    assert len(chat_provider) == 9
    assert sum(c.args[0] for c in no_retry_wait.await_args_list) == 3600
