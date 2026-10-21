"""Integration tests through the real U/T adapters and local evaluator."""

import json

import pytest

from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def saved_candidates(config, attempt):
    directory = config.attempt_dir(attempt) / 'advices'
    return [(path.joinpath('advice.txt').read_text(),
             json.loads(path.joinpath('metadata.json').read_text()))
            for path in sorted(directory.iterdir(), key=lambda path: int(path.name))]


def describe_advice_cap_loop():
    @pytest.mark.parametrize('cap,advice,rejected', [
        (5, 'abcd', False), (5, 'abcde', True), (5, 'abcdef', True),
        (5, 'abc \n', True), (5, 'éééé', False), (None, 'unlimited advice', False),
    ])
    def it_enforces_exclusive_character_bounds(config, botbox_script, cap, advice, rejected):
        config.u_advice_max_chars = cap
        botbox_script.advice.extend([advice, 'ok'] if rejected else [advice])
        botbox_script.solutions.append(PASS)

        assert run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
        candidates = saved_candidates(config, 0)
        assert candidates[0] == (advice, {'measurement': len(advice), 'rejected': rejected})
        assert len(candidates) == 1 + rejected
        assert botbox_script.t_sessions[0].messages == ['ok' if rejected else advice]
        prompts = botbox_script.u_sessions[0].messages
        assert prompts[0] == config.question_file.read_text()
        if rejected:
            assert f'Your advice was {len(advice)} characters' in prompts[1]
            assert f'fewer than {cap} characters' in prompts[1]
            assert candidates[1] == ('ok', {'measurement': 2, 'rejected': False})

    @pytest.mark.parametrize('retries', [0, 2, 10])
    def it_preserves_every_rejection_on_exhaustion(config, botbox_script, retries):
        config.u_advice_max_chars = 5
        config.u_advice_retries = retries
        botbox_script.advice.extend(['12345'] * (retries + 1))
        with pytest.raises(RuntimeError, match=f'after {retries} retries'):
            run_experiment(config, on_delta=None)
        assert len(saved_candidates(config, 0)) == retries + 1
        assert all(metadata == {'rejected': True, 'measurement': 5}
                   for _, metadata in saved_candidates(config, 0))
        assert not botbox_script.t_sessions
        assert not config.result_file.exists()
        assert (config.u_transcripts / 'session.jsonl').exists()
        assert botbox_script.u_sessions[0].closed

    def it_accepts_the_tenth_rewrite(config, botbox_script):
        config.u_advice_max_chars = 5
        botbox_script.advice.extend(['12345'] * 10 + ['ok'])
        botbox_script.solutions.append(PASS)
        run_experiment(config, on_delta=None)
        assert len(saved_candidates(config, 0)) == 11
        assert botbox_script.t_sessions[0].messages == ['ok']


def describe_u_to_t_loop():
    @pytest.mark.parametrize('failures', [0, 2, 4, 5])
    def it_stops_on_success_or_the_attempt_budget(config, botbox_script, failures):
        # Extra scripted responses reveal accidental calls after completion.
        botbox_script.advice.extend(f'advice {i}' for i in range(6))
        botbox_script.solutions.extend([FAIL] * failures + [PASS, PASS])
        result = run_experiment(config, on_delta=None)
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
        assert not (config.attempt_dir(count - 1) / 'feedback.txt').exists()
        assert all(s.closed for s in botbox_script.sessions)
        assert not botbox_script.u_sessions[0].mounts['/solutions'].exists()


def describe_combined_loops():
    def it_resets_rewrite_budget_without_spending_t_attempts(config, botbox_script):
        config.u_advice_max_chars = 5
        botbox_script.advice.extend(['12345'] * 10 + ['one'] + ['123456'] * 10 + ['two'])
        botbox_script.solutions.extend([FAIL, PASS])
        assert run_experiment(config, on_delta=None) == config.t_dir(1, 0) / 'src'
        assert [s.messages for s in botbox_script.t_sessions] == [['one'], ['two']]
        for attempt in range(2):
            candidates = saved_candidates(config, attempt)
            assert len(candidates) == 11
            assert [metadata['rejected'] for _, metadata in candidates] == [True] * 10 + [False]
        prompts = botbox_script.u_sessions[0].messages
        assert prompts[11] == (config.attempt_dir(0) / 'feedback.txt').read_text()
        assert 'Your advice was 6 characters' in prompts[12]
        assert json.loads(config.result_file.read_text())['attempts'] == 2

    @pytest.mark.parametrize('actor', ['U', 'T'])
    def it_keeps_infrastructure_errors_separate_from_test_failures(config, botbox_script, actor):
        error = RuntimeError('provider unavailable')
        botbox_script.advice.append(error if actor == 'U' else 'double it')
        botbox_script.solutions.append(error)
        with pytest.raises(RuntimeError, match='provider unavailable'):
            run_experiment(config, on_delta=None)
        assert not config.result_file.exists()
        assert not (config.t_dir(0, 0) / 'tests.json').exists()
        assert (config.u_transcripts / 'session.jsonl').exists()
        assert all(session.closed for session in botbox_script.sessions)
        if actor == 'T':
            assert 'provider unavailable' in (config.attempt_dir(0) / 'error.txt').read_text()
