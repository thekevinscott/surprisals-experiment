"""Exercise advice minimization and no-improvement streaks through the real experiment loop."""

import asyncio
import json

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_advice_improvement():
    @pytest.mark.parametrize('limit', [1, 2, 20])
    async def it_stops_without_a_first_success(config, botbox_script, limit):
        config.max_u_turns = None
        config.max_turns_without_improvement = limit
        botbox_script.advice.extend(['advice'] * 21)
        botbox_script.solutions.extend([FAIL] * 21)
        assert await run_experiment(config, on_delta=None) is None
        assert len(botbox_script.t_sessions) == limit
        assert json.loads(config.result_file.read_text())['attempts'] == limit

    @pytest.mark.parametrize('advices,outcomes,best_attempt', [
        (['long advice', 'longer advice', 'long advice'], [[PASS, PASS]] * 3, 0),
        (['long advice', 'tiny', 'x'], [[PASS, PASS], [PASS, FAIL], [FAIL, PASS]], 0),
        (['long advice', 'tiny', 'long advice', 'tiny'], [[PASS, PASS]] * 4, 1),
        (['x', 'long advice', 'tiny', 'xx', 'yyy'],
         [[FAIL, PASS], [PASS, PASS], [PASS, PASS], [FAIL, PASS], [PASS, FAIL]], 2),
    ])
    async def it_resets_only_for_strictly_shorter_all_pass_advice(
        config, botbox_script, advices, outcomes, best_attempt,
    ):
        config.max_u_turns = None
        config.max_turns_without_improvement = 2
        config.t_samples = 2
        botbox_script.advice.extend(advices + ['must not run'])
        botbox_script.solutions.extend(source for batch in outcomes for source in batch)
        result = await run_experiment(config, on_delta=None)
        assert result == config.t_dir(best_attempt, 0) / 'src'
        assert len(botbox_script.t_sessions) == 2 * len(advices)
        assert json.loads(config.result_file.read_text()) == {
            'success': True, 'attempts': len(advices), 'solution': str(result),
        }
        for attempt, advice in enumerate(advices):
            candidates = config.attempt_dir(attempt) / 'advices'
            assert [path.name for path in candidates.iterdir()] == ['0']
            assert json.loads((candidates / '0/metadata.json').read_text()) == {
                'rejected': False, 'measurement': len(advice),
            }
            assert botbox_script.t_sessions[attempt * 2].messages == [advice]
        feedback = (config.attempt_dir(len(advices) - 1) / 'feedback.txt').read_text()
        assert 'Turns without improvement: 2 of 2' in feedback
        assert f'Shortest successful advice so far: {len(advices[best_attempt])} characters' in feedback
        history = botbox_script.snapshots[-1]
        for attempt, advice in enumerate(advices[:-1]):
            assert history[f'{attempt}/advice.txt'] == advice
            for sample in range(2):
                assert history[f'{attempt}/{sample}/main.py'] == outcomes[attempt][sample]
        assert all(session.closed for session in botbox_script.sessions)

    async def it_keeps_an_explicit_fixed_cap_without_ratchet(config, botbox_script):
        config.max_u_turns = 2
        config.u_advice_max_chars = 10
        botbox_script.advice.extend(['tiny', 'longer'])
        botbox_script.solutions.extend([PASS, PASS])
        assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
        assert botbox_script.t_sessions[1].messages == ['longer']

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
