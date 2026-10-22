"""Exercise shortening and failure streaks through the real experiment loop."""

import asyncio
import json

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_ratchet():
    async def it_stops_after_twenty_consecutive_failed_batches(config, botbox_script):
        config.max_u_turns = None
        botbox_script.advice.extend(['advice'] * 21)
        botbox_script.solutions.extend([FAIL] * 21)
        assert config.max_consecutive_failures == 20
        assert await run_experiment(config, on_delta=None) is None
        assert len(botbox_script.t_sessions) == 20
        assert json.loads(config.result_file.read_text())['attempts'] == 20

    async def it_shortens_only_after_success_and_resets_the_failure_streak(config, botbox_script):
        config.max_u_turns = None
        config.max_consecutive_failures = 2
        config.t_samples = 2
        botbox_script.advice.extend(['long advice', 'short', 'short', 'longer', 'tiny', 'xx', 'yyy'])
        botbox_script.solutions.extend([FAIL, PASS, PASS, PASS, PASS, PASS, FAIL, PASS, PASS, FAIL])
        result = await run_experiment(config, on_delta=None)
        assert result == config.t_dir(2, 0) / 'src'
        assert len(botbox_script.t_sessions) == 10
        assert json.loads(config.result_file.read_text()) == {
            'success': True, 'attempts': 5, 'solution': str(result),
        }
        candidates = config.attempt_dir(2) / 'advices'
        assert [json.loads((candidates / str(i) / 'metadata.json').read_text())['rejected']
                for i in range(3)] == [True, True, False]
        # Failure at length two does not lower the last successful bound (four).
        assert botbox_script.t_sessions[-1].messages == ['yyy']
        history = botbox_script.snapshots[-1]
        for attempt, advice in enumerate(['long advice', 'short', 'tiny', 'xx']):
            assert history[f'{attempt}/advice.txt'] == advice
            for sample in range(2):
                assert history[f'{attempt}/{sample}/main.py'] in (PASS, FAIL)
        assert 'fewer than 5 characters' in botbox_script.u_sessions[0].messages[2]
        assert all(session.closed for session in botbox_script.sessions)

    @pytest.mark.parametrize('actor', ['U', 'T'])
    async def it_retains_the_best_completed_batch_on_cancellation(config, botbox_script, monkeypatch, actor):
        from conftest import FakeSession

        config.max_u_turns = None
        botbox_script.advice.extend(['long advice', 'short'])
        botbox_script.solutions.append(PASS)
        original = FakeSession.message

        async def cancel_later(session, text):
            if config.result_file.exists() and session.is_u == (actor == 'U'):
                raise asyncio.CancelledError
            return await original(session, text)

        monkeypatch.setattr(FakeSession, 'message', cancel_later)
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
        assert json.loads(config.result_file.read_text()) == {
            'success': True, 'attempts': 1, 'solution': str(config.t_dir(0, 0) / 'src'),
        }
        assert all(session.closed for session in botbox_script.sessions)
        assert (config.u_transcripts / 'session.jsonl').exists()
