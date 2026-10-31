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
    async def it_requires_every_sample_to_pass(config, botbox_script, chat_provider, n, outcome):
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
        result = await run_experiment(config, on_delta=None)
        assert (result is not None) == (outcome == 'all_pass')
        assert [s.messages for s in botbox_script.sessions] == [['double it']] * n
        assert len({id(s.agent) for s in botbox_script.sessions}) == n
        assert len(chat_provider) == 1
        assert not (config.attempt_dir(0) / 'batch.json').exists()
        for i, source in enumerate(sources):
            directory = config.t_dir(0, i)
            assert directory == config.attempt_dir(0) / 't_samples' / str(i)
            assert (directory / 'src/main.py').read_text() == source
            assert (directory / 'transcripts/session.jsonl').exists()
            assert json.loads((directory / 'tests.json').read_text())['all_passed'] == (source == PASS)
        settings = json.loads((config.output / 'settings.json').read_text())
        assert settings == {'t_samples': n, 't_sample_retries': 3}
        summary, attempt = report(config.output)
        assert summary['ts_per_advice'] == n
        assert summary['completed_t_evaluations'] == n
        assert summary['completed_evaluation_attempts'] == 1
        assert summary['evaluation_attempts_to_success'] == (1 if outcome == 'all_pass' else None)
        assert attempt['passing_ts'] == sources.count(PASS)

    async def it_returns_all_outcomes_before_revising_advice(config, botbox_script, chat_provider):
        config.t_samples = 3
        config.max_u_turns = 2
        botbox_script.advice.extend(['one', 'two'])
        botbox_script.solutions.extend([PASS, FAIL, PASS] + [PASS] * 3)
        assert await run_experiment(config, on_delta=None) == config.t_dir(1, 0) / 'src'
        assert [s.messages for s in botbox_script.sessions] == [['one']] * 3 + [['two']] * 3
        feedback = chat_provider[1]['messages'][-1]['content']
        assert feedback == (config.attempt_dir(0) / 'feedback.txt').read_text()
        assert '2 of 3 solutions passed every test' in feedback
        for i, passed in enumerate([2, 0, 2]):
            assert f'T {i}: passed {passed} of 2 tests.' in feedback
        assert json.dumps({f'T {i}': {'main.py': source} for i, source in enumerate([PASS, FAIL, PASS])},
                          indent=2) in feedback
        assert (config.attempt_dir(1) / 'feedback.txt').exists()
        assert json.loads(config.result_file.read_text())['attempts'] == 2
        summary, *_ = report(config.output)
        assert summary['advice_rewrites'] == 0
        assert summary['completed_t_evaluations'] == 6
        assert summary['evaluation_attempts_to_success'] == 2

    async def it_preserves_partial_batches_without_claiming_success(config, botbox_script):
        config.t_samples = 3
        config.t_pool_size = 1
        botbox_script.advice.append('double it')
        botbox_script.solutions.extend([PASS, RuntimeError('provider unavailable'), PASS])
        with pytest.raises(RuntimeError, match='provider unavailable'):
            await run_experiment(config, on_delta=None)
        assert len(botbox_script.sessions) >= 2
        assert not config.result_file.exists()
        assert not (config.attempt_dir(0) / 'feedback.txt').exists()
        assert (config.t_dir(0, 0) / 'src/main.py').exists()
        assert (config.t_dir(0, 0) / 'transcripts/session.jsonl').exists()
        assert not (config.t_dir(0, 0) / 'tests.json').exists()
        assert 'provider unavailable' in (config.attempt_dir(0) / 'error.txt').read_text()
        assert not (config.attempt_dir(0) / 'batch.json').exists()
        summary, attempt = report(config.output)
        assert summary['completed_evaluation_attempts'] == 0
        assert summary['completed_t_evaluations'] == 0
        assert summary['evaluation_attempts_to_success'] is None
        assert attempt['outcome'] == 'not_evaluated'

    @pytest.mark.parametrize('n', [0, -1])
    def it_rejects_nonpositive_sample_counts(config, n):
        with pytest.raises(ValidationError):
            Config(**(config.model_dump() | {'t_samples': n, 't_sample_retries': 3}))

    def it_defaults_to_five_samples_in_the_sdk(config):
        values = config.model_dump()
        del values['t_samples']
        assert Config(**values).t_samples == 5

    @pytest.mark.parametrize('args,samples,pool', [
        ([], 5, 3), (['--t-samples', '1'], 1, 3),
        (['--t-samples', '3', '--t-pool-size', '2'], 3, 2),
    ])
    async def it_accepts_the_cli_flag(config, monkeypatch, args, samples, pool):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        received = []
        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: 'unused')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        async def run(config, **kwargs):
            received.append(config)
        monkeypatch.setattr(cli, 'run_experiment', run)
        await cli.main(['--output', str(config.output), *args, 'problem', str(config.problem_dir)])
        assert received[0].t_samples == samples
        assert received[0].t_pool_size == pool
