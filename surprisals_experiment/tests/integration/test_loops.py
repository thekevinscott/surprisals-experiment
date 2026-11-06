"""Integration tests through the real U/T adapters and local evaluator."""

import asyncio
import json
from advice_artifacts import advice_directory, read_score

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def turns(config, window):
    return sorted(int(path.name) for path in (config.output / f'windows/{window}/forks/0/turns').iterdir())


def describe_u_to_t_loop():
    @pytest.mark.parametrize('failures', [0, 2])
    async def it_records_each_batch_with_an_explicit_iteration_limit(config, botbox_script, chat_provider, failures):
        count = min(failures + 1, 5)
        config.max_u_turns = count
        # Extra scripted responses reveal accidental calls after completion.
        botbox_script.advice.extend(f'advice {i}' for i in range(2 * count + 6))
        botbox_script.solutions.extend([FAIL] * failures + [PASS] + [FAIL] * count + [PASS])
        result = await run_experiment(config, on_delta=None)
        expected = config.t_dir(count - 1, 0) / 'src' if failures < 5 else None
        assert result == expected
        assert json.loads(config.result_file.read_text()) == {
            'success': failures < 5, 'attempts': 2 * count,
            'solution': str(expected) if expected else None,
        }
        assert turns(config, 0) == turns(config, 1) == list(range(count))
        assert len(botbox_script.advice) == 6
        assert len(botbox_script.sessions) == 2 * count
        assert [s.messages for s in botbox_script.sessions[:count]] == [[f'advice {i}'] for i in range(count)]
        for i in range(count):
            tests = json.loads((config.t_dir(i, 0) / 'tests.json').read_text())
            assert tests['passed'] == (2 if i == failures else 0)
            assert (config.t_dir(i, 0) / 'transcripts/session.jsonl').exists()
            if i + 1 < count:
                feedback = chat_provider[i + 1]['messages'][-1]['content']
                assert feedback == (config.problem_dir / 'question.txt').read_text()
        assert config.error_file.exists() == (failures == 5)
        assert all(s.closed for s in botbox_script.sessions)


def describe_advice_improvement():
    async def it_stops_without_a_first_success(config, botbox_script):
        limit = 2
        config.max_u_turns = limit
        botbox_script.advice.extend(['advice'] * 21)
        botbox_script.solutions.extend([FAIL] * 21)
        assert await run_experiment(config, on_delta=None) is None
        assert turns(config, 0) == turns(config, 1) == list(range(limit))
        assert len(botbox_script.sessions) == 2 * limit
        assert json.loads(config.result_file.read_text())['attempts'] == 2 * limit

    @pytest.mark.parametrize('advices,outcomes,best_attempt', [
        (['long advice', 'tiny', 'long advice', 'tiny'], [[PASS, PASS]] * 4, 1),
        (['long advice', 'tiny', 'x'], [[PASS, PASS], [PASS, FAIL], [FAIL, PASS]], 0),
    ])
    async def it_selects_only_strictly_shorter_all_pass_advice(
        config, botbox_script, chat_provider, advices, outcomes, best_attempt,
    ):
        config.max_u_turns = len(advices)
        config.t_samples = 2
        botbox_script.advice.extend(advices + ['window 1'] * len(advices) + ['must not run'])
        botbox_script.solutions.extend(source for batch in outcomes for source in batch)
        botbox_script.solutions.extend([FAIL] * 2 * len(advices))
        result = await run_experiment(config, on_delta=None)
        assert result == config.t_dir(best_attempt, 0) / 'src'
        assert list(botbox_script.advice) == ['must not run']
        assert len(botbox_script.sessions) == 4 * len(advices)
        assert json.loads(config.result_file.read_text()) == {
            'success': True, 'attempts': 2 * len(advices), 'solution': str(result),
        }
        for attempt, advice in enumerate(advices):
            assert json.loads((config.attempt_dir(attempt) / 'metadata.json').read_text()) == {
                'advice': str(advice_directory(config, advice).relative_to(config.output)),
            }
            assert botbox_script.sessions[attempt * 2].messages == [advice]
        feedback = chat_provider[len(advices)]['messages'][-1]['content']
        assert f'<index>{best_attempt}</index>' in feedback
        assert f'<length>{len(advices[best_attempt])} characters</length>' in feedback
        assert all(session.closed for session in botbox_script.sessions)

    async def it_retains_the_best_completed_batch_on_cancellation(config, botbox_script, chat_provider):
        config.max_u_turns = None
        botbox_script.advice.extend(['long advice', 'short'])
        botbox_script.solutions.extend([PASS, asyncio.Event()])
        run = asyncio.create_task(run_experiment(config, on_delta=None))
        async with asyncio.timeout(5):
            while len(botbox_script.sessions) < 2:
                await asyncio.sleep(0.01)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        assert not config.result_file.exists()
        assert '<advice>\nlong advice\n</advice>' in chat_provider[1]['messages'][-1]['content']
        assert json.loads((config.t_dir(0, 0) / 'tests.json').read_text())['all_passed']
        assert not (config.t_dir(1, 0) / 'tests.json').exists()
        assert all(session.closed for session in botbox_script.sessions)
        assert (config.u_transcripts / 'messages.jsonl').exists()


def describe_run_layout():
    async def it_nests_each_turn_under_window_and_fork(config, botbox_script):
        config.max_u_turns = 2
        botbox_script.advice.extend(['long advice', 'short', 'window 1', 'window 1'])
        botbox_script.solutions.extend([PASS, PASS, FAIL, FAIL])
        await run_experiment(config, on_delta=None)
        window = config.output / 'windows/0'
        fork = window / 'forks/0'
        assert json.loads((window / 'window.json').read_text()) == {}
        assert json.loads((fork / 'fork.json').read_text()) == {}
        assert sorted(path.name for path in (fork / 'turns').iterdir()) == ['0', '1']
        for turn, advice in enumerate(['long advice', 'short']):
            directory = fork / 'turns' / str(turn)
            assert (advice_directory(config, advice) / 'advice.txt').read_text() == advice
            assert read_score(config, turn)['score'] == len(advice)
            assert (directory / 'ts/0/tests.json').exists()
            assert (directory / 'ts/0/src/main.py').read_text() == PASS
        assert not (config.output / 'attempts').exists()
