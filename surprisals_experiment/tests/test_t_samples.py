"""Independent T batches through the actual feedback loop and evaluator."""

import json
import importlib

import pytest
from pydantic import ValidationError

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from test_run_summary import report

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_n_of_t():
    @pytest.mark.parametrize('n', [1, 3, 5])
    @pytest.mark.parametrize('outcome', ['all_pass', 'first_fails', 'last_fails', 'all_fail'])
    def it_requires_every_sample_to_pass(config, botbox_script, n, outcome):
        config.t_samples = n
        config.max_u_turns = 1
        sources = [PASS] * n
        if outcome == 'first_fails':
            sources[0] = FAIL
        elif outcome == 'last_fails':
            sources[-1] = FAIL
        elif outcome == 'all_fail':
            sources = [FAIL] * n
        botbox_script.advice.append('double it')
        botbox_script.solutions.extend(sources)
        result = run_experiment(config, on_delta=None)
        assert (result is not None) == (outcome == 'all_pass')
        assert [s.messages for s in botbox_script.t_sessions] == [['double it']] * n
        assert len({id(s.agent) for s in botbox_script.t_sessions}) == n
        assert len(botbox_script.u_sessions[0].messages) == 1
        batch = json.loads((config.attempt_dir(0) / 'batch.json').read_text())
        assert batch == {'expected': n, 'completed': n, 'passed': sources.count(PASS),
                         'tests_passed': sources.count(PASS) * 2, 'tests_total': n * 2,
                         'all_passed': outcome == 'all_pass'}
        for i, source in enumerate(sources):
            directory = config.t_dir(0, i)
            assert (directory / 'src/main.py').read_text() == source
            assert (directory / 't_transcripts/session.jsonl').exists()
            assert json.loads((directory / 'tests.json').read_text())['all_passed'] == (source == PASS)
        settings = json.loads((config.output / 'settings.json').read_text())
        assert settings == {'u_advice_max_chars': None}
        summary, attempt = report(config.output)
        assert summary['ts_per_advice'] == n
        assert summary['completed_t_evaluations'] == n
        assert summary['completed_evaluation_attempts'] == 1
        assert summary['evaluation_attempts_to_success'] == (1 if outcome == 'all_pass' else None)
        assert attempt['passing_ts'] == sources.count(PASS)

    def it_returns_all_outcomes_before_revising_advice(config, botbox_script):
        config.t_samples = 3
        config.u_advice_max_chars = 5
        config.u_advice_retries = 1
        botbox_script.advice.extend(['too long', 'one', 'too long again', 'two'])
        botbox_script.solutions.extend([PASS, FAIL, PASS] + [PASS] * 3)
        assert run_experiment(config, on_delta=None) == config.t_dir(1, 0) / 'src'
        assert [s.messages for s in botbox_script.t_sessions] == [['one']] * 3 + [['two']] * 3
        feedback = botbox_script.u_sessions[0].messages[2]
        assert feedback == (config.attempt_dir(0) / 'feedback.txt').read_text()
        assert '2 of 3 solutions passed every test' in feedback
        for i, passed in enumerate([2, 0, 2]):
            assert f'T {i}: solution in /solutions/0/{i}; passed {passed} of 2 tests.' in feedback
        assert botbox_script.snapshots[2] == {
            '0/0/main.py': PASS, '0/1/main.py': FAIL, '0/2/main.py': PASS,
        }
        assert not (config.attempt_dir(1) / 'feedback.txt').exists()
        assert json.loads(config.result_file.read_text())['attempts'] == 2
        summary, *_ = report(config.output)
        assert summary['advice_rewrites'] == 2
        assert summary['completed_t_evaluations'] == 6
        assert summary['evaluation_attempts_to_success'] == 2

    def it_preserves_partial_batches_without_claiming_success(config, botbox_script):
        config.t_samples = 3
        botbox_script.advice.append('double it')
        botbox_script.solutions.extend([PASS, RuntimeError('provider unavailable'), PASS])
        with pytest.raises(RuntimeError, match='provider unavailable'):
            run_experiment(config, on_delta=None)
        assert len(botbox_script.t_sessions) == 2
        assert not config.result_file.exists()
        assert not (config.attempt_dir(0) / 'feedback.txt').exists()
        assert (config.t_dir(0, 0) / 'tests.json').exists()
        assert 'provider unavailable' in (config.attempt_dir(0) / 'error.txt').read_text()
        assert json.loads((config.attempt_dir(0) / 'batch.json').read_text()) == {
            'expected': 3, 'completed': 1, 'passed': 1, 'all_passed': False,
            'tests_passed': 2, 'tests_total': 2,
        }
        summary, attempt = report(config.output)
        assert summary['completed_evaluation_attempts'] == 0
        assert summary['completed_t_evaluations'] == 1
        assert summary['evaluation_attempts_to_success'] is None
        assert attempt['outcome'] == 'incomplete_batch'

    @pytest.mark.parametrize('n', [0, -1])
    def it_rejects_nonpositive_sample_counts(config, n):
        with pytest.raises(ValidationError):
            Config(**(config.model_dump() | {'t_samples': n}))

    def it_defaults_to_five_samples_in_the_sdk(config):
        values = config.model_dump()
        del values['t_samples']
        assert Config(**values).t_samples == 5

    @pytest.mark.parametrize('args,expected', [([], 5), (['--t-samples', '1'], 1), (['--t-samples', '3'], 3)])
    def it_accepts_the_cli_flag(config, monkeypatch, args, expected):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        received = []
        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: 'unused')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        monkeypatch.setattr(cli, 'run_experiment', lambda config, **kwargs: received.append(config))
        cli.main(['--output', str(config.output), *args, 'problem', str(config.problem_dir)])
        assert received[0].t_samples == expected
