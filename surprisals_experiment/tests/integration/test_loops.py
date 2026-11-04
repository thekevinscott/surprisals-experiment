"""Integration tests through the real U/T adapters and local evaluator."""

import asyncio
import json

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_u_to_t_loop():
    @pytest.mark.parametrize('failures', [0, 2])
    async def it_records_each_batch_with_an_explicit_iteration_limit(config, botbox_script, chat_provider, failures):
        config.max_u_turns = min(failures + 1, 5)
        # Extra scripted responses reveal accidental calls after completion.
        botbox_script.advice.extend(f'advice {i}' for i in range(6))
        botbox_script.solutions.extend([FAIL] * failures + [PASS, PASS])
        result = await run_experiment(config, on_delta=None)
        count = min(failures + 1, 5)
        expected = config.t_dir(count - 1, 0) / 'src' if failures < 5 else None
        assert result == expected
        assert json.loads(config.result_file.read_text()) == {
            'success': failures < 5, 'attempts': count,
            'solution': str(expected) if expected else None,
        }
        assert len(botbox_script.sessions) == count
        assert [s.messages for s in botbox_script.sessions] == [[f'advice {i}'] for i in range(count)]
        for i in range(count):
            attempt = config.attempt_dir(i)
            tests = json.loads((config.t_dir(i, 0) / 'tests.json').read_text())
            assert tests['passed'] == (2 if i == failures else 0)
            assert (config.t_dir(i, 0) / 'transcripts/session.jsonl').exists()
            if i + 1 < count:
                feedback = (attempt / 'feedback.txt').read_text()
                assert 'passed 0 of 2 tests' in feedback
                assert '"main.py": "print(0)\\n"' in feedback
                assert chat_provider[i + 1]['messages'][-1]['content'] == feedback
        assert config.error_file.exists() == (failures == 5)
        assert (config.attempt_dir(count - 1) / 'feedback.txt').exists()
        assert all(s.closed for s in botbox_script.sessions)


def implementations(sources):
    return json.dumps({f'T {index}': {'main.py': source} for index, source in enumerate(sources)}, indent=2)


def describe_advice_improvement():
    async def it_stops_without_a_first_success(config, botbox_script):
        limit = 2
        config.max_u_turns = None
        config.max_turns_without_improvement = limit
        botbox_script.advice.extend(['advice'] * 21)
        botbox_script.solutions.extend([FAIL] * 21)
        assert await run_experiment(config, on_delta=None) is None
        assert len(botbox_script.sessions) == limit
        assert json.loads(config.result_file.read_text())['attempts'] == limit

    @pytest.mark.parametrize('advices,outcomes,best_attempt', [
        (['long advice', 'tiny', 'long advice', 'tiny'], [[PASS, PASS]] * 4, 1),
        (['long advice', 'tiny', 'x'], [[PASS, PASS], [PASS, FAIL], [FAIL, PASS]], 0),
    ])
    async def it_resets_only_for_strictly_shorter_all_pass_advice(
        config, botbox_script, chat_provider, advices, outcomes, best_attempt,
    ):
        config.max_u_turns = None
        config.max_turns_without_improvement = 2
        config.t_samples = 2
        botbox_script.advice.extend(advices + ['must not run'])
        botbox_script.solutions.extend(source for batch in outcomes for source in batch)
        result = await run_experiment(config, on_delta=None)
        assert result == config.t_dir(best_attempt, 0) / 'src'
        assert len(botbox_script.sessions) == 2 * len(advices)
        assert json.loads(config.result_file.read_text()) == {
            'success': True, 'attempts': len(advices), 'solution': str(result),
        }
        for attempt, advice in enumerate(advices):
            candidates = config.attempt_dir(attempt) / 'advices'
            assert [path.name for path in candidates.iterdir()] == ['0']
            assert json.loads((candidates / '0/metadata.json').read_text()) == {
                'rejected': False, 'measurement': len(advice),
            }
            assert botbox_script.sessions[attempt * 2].messages == [advice]
        feedback = (config.attempt_dir(len(advices) - 1) / 'feedback.txt').read_text()
        assert 'Turns without improvement: 2 of 2' in feedback
        assert f'Shortest successful advice so far: {len(advices[best_attempt])} characters' in feedback
        history = chat_provider[-1]['messages']
        for attempt, advice in enumerate(advices[:-1]):
            assert history[2 * attempt + 2]['content'] == advice
            assert implementations(outcomes[attempt]) in history[2 * attempt + 3]['content']
        assert all(session.closed for session in botbox_script.sessions)


    async def it_retains_the_best_completed_batch_on_cancellation(config, botbox_script, monkeypatch):
        from conftest import FakeSession

        config.max_u_turns = None
        botbox_script.advice.extend(['long advice', 'short'])
        botbox_script.solutions.append(PASS)
        owner, method = FakeSession, 'message'
        original = getattr(owner, method)

        async def cancel_later(session, *args, **kwargs):
            if config.result_file.exists():
                raise asyncio.CancelledError
            return await original(session, *args, **kwargs)

        monkeypatch.setattr(owner, method, cancel_later)
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
        assert json.loads(config.result_file.read_text()) == {
            'success': True, 'attempts': 1, 'solution': str(config.t_dir(0, 0) / 'src'),
        }
        assert all(session.closed for session in botbox_script.sessions)
        assert (config.u_transcripts / 'messages.jsonl').exists()
