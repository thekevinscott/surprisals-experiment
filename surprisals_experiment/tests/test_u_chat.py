"""Chat U uses real SDK streaming with HTTP mocked by the global fixture."""

import json
from contextlib import nullcontext

import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_session import open_u_session

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_chat_u():
    @pytest.mark.parametrize('thinking,reasoning', [
        ('off', {'enabled': False}), ('high', {'effort': 'high'}),
        ('xhigh', {'effort': 'xhigh'}),
    ])
    async def it_preserves_conversation_and_streams_advice(
        config, botbox_script, chat_provider, thinking, reasoning,
    ):
        config.u_mode = 'chat'
        config.u_thinking = thinking
        botbox_script.advice.extend(['first\nadvice', 'next'])
        deltas = []
        async with open_u_session(config) as session:
            assert await session.prompt('question', on_delta=lambda *delta: deltas.append(delta)) == 'first\nadvice'
            assert await session.prompt('feedback') == 'next'
        assert not botbox_script.sessions
        assert chat_provider[0]['reasoning'] == reasoning
        assert 'tools' not in chat_provider[0]
        assert [message['role'] for message in chat_provider[1]['messages']] == [
            'system', 'user', 'assistant', 'user',
        ]
        assert chat_provider[1]['messages'][2]['content'] == 'first\nadvice'
        assert chat_provider[1]['messages'][2]['reasoning'] == 'Thinking.'
        assert ''.join(text for kind, text in deltas if kind == 'text') == 'first\nadvice'
        assert ('thinking', 'Thinking.') in deltas
        transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        assert len(transcript) == 5
        assert transcript[-1]['content'] == 'next'
        assert not session.solutions.exists()

    async def it_feeds_every_t_source_and_result_back_before_the_next_turn(
        config, botbox_script, chat_provider, monkeypatch,
    ):
        from conftest import FakeSession

        config.u_mode = 'chat'
        config.t_samples = 2
        config.max_u_turns = 2
        botbox_script.advice.extend(['long advice', 'short'])
        failed_code = "from pathlib import Path\nPath('evaluation-only.txt').write_text(input())\nprint(0)\n"
        botbox_script.solutions.extend([failed_code, PASS, PASS, PASS])
        original = FakeSession.message

        async def write_helpers(session, text):
            result = await original(session, text)
            output = session.mounts['/solution']
            (output / 'helper.py').write_text('VALUE = 42\n')
            (output / 'nested').mkdir()
            (output / 'nested/extra.py').write_text('EXTRA = 7\n')
            (output / 'binary.dat').write_bytes(b'\xff')
            (output / 'hidden.json').symlink_to(config.test_suite_file)
            return result

        monkeypatch.setattr(FakeSession, 'message', write_helpers)
        assert await run_experiment(config, on_delta=None) == config.t_dir(1, 0) / 'src'
        assert not botbox_script.u_sessions
        assert len(botbox_script.t_sessions) == 4
        feedback = chat_provider[1]['messages'][-1]['content']
        assert feedback == (config.attempt_dir(0) / 'feedback.txt').read_text()
        assert '/solutions/' not in feedback
        assert 'Your advice was 11 characters' in feedback
        assert 'T 0: passed 0 of 2 tests.' in feedback
        assert 'T 1: passed 2 of 2 tests.' in feedback
        assert feedback.count('"helper.py": "VALUE = 42\\n"') == 2
        assert feedback.count('"nested/extra.py": "EXTRA = 7\\n"') == 2
        assert json.dumps(failed_code) in feedback
        assert '"evaluation-only.txt":' not in feedback
        assert json.dumps(PASS) in feedback
        assert 'read and ls tools' not in feedback
        assert '"hidden.json":' not in feedback
        assert '"binary.dat":' not in feedback


    @pytest.mark.parametrize('finish', [None, 'length', 'content_filter'])
    async def it_rejects_incomplete_advice_but_retains_the_transcript(
        config, botbox_script, finish,
    ):
        config.u_mode = 'chat'
        botbox_script.advice.extend([{
            'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': finish,
        }] * 9)
        with pytest.raises(RuntimeError, match='U chat'):
            await run_experiment(config, on_delta=None)
        assert not botbox_script.t_sessions
        assert 'partial' in (config.u_transcripts / 'messages.jsonl').read_text()

    async def it_preserves_the_prompt_on_provider_failure(config, botbox_script):
        config.u_mode = 'chat'
        botbox_script.advice.append({'status': 400})
        with pytest.raises(RuntimeError, match='provider failed'):
            await run_experiment(config, on_delta=None)
        assert not botbox_script.t_sessions
        assert config.question_file.read_text() in (config.u_transcripts / 'messages.jsonl').read_text()

    def it_defaults_to_agent(config):
        values = config.model_dump()
        values.pop('u_mode')
        assert Config(**values).u_mode == 'agent'

    async def it_keeps_reasoning_details_in_the_next_request(config, botbox_script, chat_provider):
        config.u_mode = 'chat'
        details = {'type': 'reasoning.text', 'text': 'Reasoning', 'index': 0}
        botbox_script.advice.extend([
            {'deltas': [{'role': 'assistant', 'reasoning_details': [details], 'content': 'advice'}]},
            'next',
        ])
        deltas = []
        async with open_u_session(config) as session:
            await session.prompt('question', on_delta=lambda *delta: deltas.append(delta))
            await session.prompt('feedback')
        assert chat_provider[1]['messages'][2]['reasoning_details'] == [details]
        assert ('thinking', 'Reasoning') in deltas

    async def it_stops_without_improvement_and_retains_all_prior_batches(
        config, botbox_script, chat_provider,
    ):
        config.u_mode = 'chat'
        config.max_u_turns = None
        config.max_turns_without_improvement = 2
        botbox_script.advice.extend(['tiny', 'long advice', 'longer advice'])
        botbox_script.solutions.extend([PASS] * 3)
        assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
        assert len(chat_provider) == 3
        history = chat_provider[-1]['messages']
        assert [m['content'] for m in history if m['role'] == 'assistant'] == ['tiny', 'long advice']
        assert sum(json.dumps(PASS) in m['content'] for m in history if m['role'] == 'user') == 2
        assert json.loads((config.output / 'settings.json').read_text())['u_mode'] == 'chat'

    @pytest.mark.parametrize('args,mode', [
        (['--u-mode', 'chat'], 'chat'), (['--u-mode', 'agent'], 'agent'), ([], 'agent'),
    ])
    async def it_wires_the_cli_mode(monkeypatch, tmp_path, args, mode):
        import importlib
        cli = importlib.import_module('surprisals_experiment.cli.main')
        received = []

        async def run(config, **kwargs):
            received.append(config.u_mode)

        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused/.env')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        monkeypatch.setattr(cli, 'run_experiment', run)
        await cli.main([
            '--output', str(tmp_path / 'run'), 'problem', str(tmp_path), *args,
        ])
        assert received == [mode]

    async def it_saves_partial_output_on_cancellation(config, botbox_script):
        import asyncio

        config.u_mode = 'chat'
        botbox_script.advice.append('advice')

        def cancel(kind, text):
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            async with open_u_session(config) as session:
                await session.prompt('question', on_delta=cancel)
        transcript = (config.u_transcripts / 'messages.jsonl').read_text()
        assert 'Thinking.' in transcript
        assert not session.solutions.exists()

    @pytest.mark.parametrize('deltas', [[], [{'role': 'assistant'}]])
    async def it_does_not_accept_empty_replies(config, botbox_script, deltas):
        config.u_mode = 'chat'
        botbox_script.advice.extend([{'deltas': deltas, 'finish': None}] * 9)
        with pytest.raises(RuntimeError, match='U chat'):
            await run_experiment(config, on_delta=None)
        assert not botbox_script.t_sessions


ROLES = {'system', 'user', 'assistant'}


def describe_chat_u_roles():
    async def it_sends_and_records_exact_roles_when_every_chunk_repeats_the_role(
        config, botbox_script, chat_provider,
    ):
        config.u_mode = 'chat'
        config.max_u_turns = 3
        chunked = lambda text: {'deltas': [{'role': 'assistant', 'content': c} for c in text]}
        botbox_script.advice.extend([chunked('long advice'), chunked('shorter'), chunked('short')])
        botbox_script.solutions.extend([PASS, PASS, PASS])
        await run_experiment(config, on_delta=None)
        assert len(chat_provider) == 3
        for request in chat_provider:
            assert {m['role'] for m in request['messages']} <= ROLES
        assert [m['content'] for m in chat_provider[-1]['messages'] if m['role'] == 'assistant'] == [
            'long advice', 'shorter',
        ]
        transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        assert {m['role'] for m in transcript} <= ROLES
        assert [m['content'] for m in transcript if m['role'] == 'assistant'] == [
            'long advice', 'shorter', 'short',
        ]

    async def it_records_an_exact_role_for_reasoning_chunks(config, botbox_script, chat_provider):
        config.u_mode = 'chat'
        botbox_script.advice.append({'deltas': [
            {'role': 'assistant', 'reasoning': 'Thinking.'},
            {'role': 'assistant', 'reasoning': ' More.'},
            {'role': 'assistant', 'content': 'advice'},
        ]})
        async with open_u_session(config) as session:
            assert await session.prompt('question') == 'advice'
        assert session.messages[-1]['role'] == 'assistant'
        assert session.messages[-1]['reasoning'] == 'Thinking. More.'

    @pytest.mark.parametrize('finish', [None, 'length'])
    async def it_records_an_exact_role_for_an_incomplete_reply(config, botbox_script, finish):
        config.u_mode = 'chat'
        botbox_script.advice.extend([{
            'deltas': [{'role': 'assistant', 'content': 'par'}, {'role': 'assistant', 'content': 'tial'}],
            'finish': finish,
        }] * 9)
        with pytest.raises(RuntimeError, match='U chat'):
            await run_experiment(config, on_delta=None)
        transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        assert transcript[-1] == {'role': 'assistant', 'content': 'partial'}


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())


@pytest.mark.parametrize('final_format', ['unknown', 'provider.v1'])
@pytest.mark.parametrize('finish', ['stop', None, 'length'])
async def test_reasoning_format_preserves_latest_provider_value(
    config, botbox_script, chat_provider, final_format, finish,
):
    config.u_mode = 'chat'
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
    botbox_script.advice.append('next')
    expected = [
        {'type': 'reasoning.text', 'index': 0, 'text': 'Think more.', 'format': final_format},
        {'type': 'reasoning.text', 'index': 1, 'text': 'Other thought', 'format': 'other'},
    ]
    async with open_u_session(config) as session:
        with nullcontext() if finish == 'stop' else pytest.raises(RuntimeError):
            await session.prompt('question')
        assert session.messages[-1]['reasoning_details'] == expected
        transcript = [json.loads(line) for line in session.transcript.read_text().splitlines()]
        assert transcript[-1]['reasoning_details'] == expected
        assert transcript[-1]['content'] == 'advice'
        if finish == 'stop':
            await session.prompt('feedback')
            assert chat_provider[-1]['messages'][2]['reasoning_details'] == expected
