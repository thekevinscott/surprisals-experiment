"""Integration tests through the real U/T adapters and local evaluator."""

import json

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'






def describe_u_to_t_loop():
    @pytest.mark.parametrize('failures', [0, 2, 4, 5])
    async def it_records_each_batch_with_an_explicit_iteration_limit(config, botbox_script, failures):
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
        assert len(botbox_script.u_sessions) == 1
        assert len(botbox_script.t_sessions) == count
        assert [s.messages for s in botbox_script.t_sessions] == [[f'advice {i}'] for i in range(count)]
        for i in range(count):
            attempt = config.attempt_dir(i)
            tests = json.loads((config.t_dir(i, 0) / 'tests.json').read_text())
            assert tests['passed'] == (2 if i == failures else 0)
            assert (config.t_dir(i, 0) / 't_transcripts/session.jsonl').exists()
            if i + 1 < count:
                feedback = (attempt / 'feedback.txt').read_text()
                assert 'passed 0 of 2 tests' in feedback
                assert f'/solutions/{i}' in feedback
                assert botbox_script.u_sessions[0].messages[i + 1] == feedback
                assert botbox_script.snapshots[i + 1][f'{i}/0/main.py'] == FAIL
        assert config.error_file.exists() == (failures == 5)
        assert (config.attempt_dir(count - 1) / 'feedback.txt').exists()
        assert all(s.closed for s in botbox_script.sessions)
        assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()


def describe_combined_loops():

    @pytest.mark.parametrize('actor', ['U', 'T'])
    async def it_keeps_infrastructure_errors_separate_from_test_failures(config, botbox_script, actor):
        error = RuntimeError('provider unavailable')
        botbox_script.advice.append(error if actor == 'U' else 'double it')
        botbox_script.solutions.append(error)
        with pytest.raises(RuntimeError, match='provider unavailable'):
            await run_experiment(config, on_delta=None)
        assert not config.result_file.exists()
        assert not (config.t_dir(0, 0) / 'tests.json').exists()
        assert (config.u_transcripts / 'session.jsonl').exists()
        assert all(session.closed for session in botbox_script.sessions)
        if actor == 'T':
            assert 'provider unavailable' in (config.attempt_dir(0) / 'error.txt').read_text()
