"""Exercise compaction through real chat streaming with the global HTTP mock."""

import json

import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_session import open_u_session

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_chat_compaction():
    async def it_keeps_measured_best_and_streak_across_repeated_compactions(
        config, botbox_script, chat_provider,
    ):
        config.u_mode = 'chat'
        config.u_compact_chars = 1
        config.max_u_turns = 4
        # First success; then shorter but failing; then a new best; then no improvement.
        best = 'double\n"input" {exact}'
        botbox_script.advice.extend([
            best, 'Failures: none. Best length is 999 (incorrect summary).', 'x',
            'Do not print zero.', 'double', 'Remember integer parsing.', 'longer advice',
        ])
        botbox_script.solutions.extend([PASS, FAIL, PASS, PASS])
        assert await run_experiment(config, on_delta=None) == config.t_dir(2, 0) / 'src'
        assert len(chat_provider) == 7
        system = chat_provider[0]['messages'][0]
        assert 'except when explicitly asked to summarize' in system['content']
        for request_index, attempt, advice, length, streak in [
            (2, 0, best, len(best), 0), (4, 1, best, len(best), 1), (6, 2, 'double', 6, 0),
        ]:
            messages = chat_provider[request_index]['messages']
            assert len(messages) == 3
            assert messages[0] == system
            preamble = messages[1]['content']
            assert config.question_file.read_text() in preamble
            assert f'<best_successful_advice>\n{advice}\n</best_successful_advice>' in preamble
            assert f'Best successful advice length: {length}' in preamble
            assert f'Turns without improvement: {streak}' in preamble
            assert messages[2]['content'] == (config.attempt_dir(attempt) / 'feedback.txt').read_text()
        assert json.dumps(FAIL) in chat_provider[4]['messages'][2]['content']
        transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        assert len(transcript) == 18  # system + four advice exchanges + three summary exchanges/preambles
        assert [m['content'] for m in transcript if m['role'] == 'assistant'] == [
            best, 'Failures: none. Best length is 999 (incorrect summary).', 'x',
            'Do not print zero.', 'double', 'Remember integer parsing.', 'longer advice',
        ]
        assert len(botbox_script.t_sessions) == 4
        assert not botbox_script.advice

    @pytest.mark.parametrize('compact_chars', [0, 400000])
    async def it_leaves_history_intact_when_disabled_or_below_threshold(
        config, botbox_script, chat_provider, compact_chars,
    ):
        config.u_mode = 'chat'
        config.u_compact_chars = compact_chars
        botbox_script.advice.extend(['first', 'second'])
        async with open_u_session(config) as session:
            await session.prompt('question')
            await session.prompt('feedback')
        assert len(chat_provider) == 2
        assert len(chat_provider[-1]['messages']) == 4

    @pytest.mark.parametrize('over_by,expected_requests', [(0, 2), (1, 3)])
    async def it_counts_reasoning_and_pending_feedback_at_the_threshold(
        config, botbox_script, chat_provider, over_by, expected_requests,
    ):
        config.u_mode = 'chat'
        botbox_script.advice.extend(['first', 'summary', 'second'])
        async with open_u_session(config) as session:
            await session.prompt('question')
            pending = 'feedback' * 100
            session.compact_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in session.messages) + len(pending) - over_by
            await session.prompt(pending)
        assert len(chat_provider) == expected_requests
        assert chat_provider[-1]['messages'][-1]['content'] == pending

    async def it_compacts_rejected_rewrites_without_sending_the_summary_to_t(
        config, botbox_script, chat_provider,
    ):
        config.u_mode = 'chat'
        config.u_compact_chars = 1
        config.u_advice_max_chars = 5
        botbox_script.advice.extend(['too long', 'Prior advice exceeded the cap.', 'ok'])
        botbox_script.solutions.append(PASS)
        await run_experiment(config, on_delta=None)
        assert 'fewer than 5' in chat_provider[-1]['messages'][-1]['content']
        preamble = chat_provider[-1]['messages'][1]['content']
        assert 'Best successful advice length: None' in preamble
        assert 'Turns without improvement: 0' in preamble
        assert (config.advice_dir(0, 1) / 'advice.txt').read_text() == 'ok'
        assert len(botbox_script.t_sessions) == 1

    @pytest.mark.parametrize('summary', ['x' * 2000, {'status': 400}])
    async def it_preserves_history_and_previous_result_on_summary_failure(
        config, botbox_script, summary,
    ):
        config.u_mode = 'chat'
        config.u_compact_chars = 1
        config.max_u_turns = 2
        botbox_script.advice.extend(['good', summary])
        botbox_script.solutions.append(PASS)
        with pytest.raises(RuntimeError):
            await run_experiment(config, on_delta=None)
        assert json.loads(config.result_file.read_text())['attempts'] == 1
        transcript = (config.u_transcripts / 'messages.jsonl').read_text()
        assert 'good' in transcript
        assert 'Pause advice generation' in transcript
        assert 'We compacted' not in transcript
        assert len(botbox_script.t_sessions) == 1
        assert all(session.closed for session in botbox_script.sessions)

    async def it_leaves_agent_mode_unchanged(config, botbox_script, chat_provider):
        config.u_compact_chars = 1
        config.max_u_turns = 2
        botbox_script.advice.extend(['long', 'ok'])
        botbox_script.solutions.extend([PASS, PASS])
        await run_experiment(config, on_delta=None)
        assert not chat_provider
        assert len(botbox_script.u_sessions[0].messages) == 2

    def it_defaults_to_400000_and_rejects_negative_values(config):
        assert config.u_compact_chars == 400000
        with pytest.raises(ValueError, match='u_compact_chars'):
            Config(**(config.model_dump() | {'u_compact_chars': -1}))

    async def it_wires_the_cli_flag(config, monkeypatch):
        import importlib
        cli = importlib.import_module('surprisals_experiment.cli.main')
        received = []

        async def run(settings, **kwargs):
            received.append(settings.u_compact_chars)

        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused/.env')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        monkeypatch.setattr(cli, 'run_experiment', run)
        await cli.main([
            '--u-compact-chars', '1234', '--output', str(config.output), 'problem', str(config.problem_dir),
        ])
        assert received == [1234]
